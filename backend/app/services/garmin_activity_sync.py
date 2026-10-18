"""Synchronise Garmin Connect activities into our database.

Garmin is the main source of activities (it has the heart rate). One run does,
like the Strava sync:

1. **New activities**: the most recent pages, until we reach activities we
   already have (minus a few days of overlap, to pick up edits).
2. **History**: a few more pages of older activities, from where the previous
   run stopped (``sync_cursor`` "garmin_activities_backfill"), until Garmin
   returns an empty page.
3. **Details**: heart rate, GPS, altitude and speed samples of activities that
   don't have them yet, a limited number per run.
4. **Duplicates**: Strava copies of these activities are recognised and left
   out (``app/services/dedupe.py``).

Garmin's list is paged by *offset* (0 = most recent). New activities shift the
offsets a little, so a history page may re-read a few activities: the upsert
makes that harmless, and nothing is ever skipped.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import SyncLog
from app.db.models.enums import DataSource, SyncKind, SyncStatus
from app.integrations.health.garmin_activities import (
    GarminActivitySummary,
    activity_fields,
    details_to_series,
    summary_polyline,
)
from app.integrations.health.garmin_connect import GarminApi, call_garmin
from app.integrations.health.provider import HealthProviderError, HealthRateLimitedError
from app.repositories import activities as activities_repo
from app.repositories import sync as sync_repo
from app.services.dedupe import reconcile_duplicates
from app.services.stream_codec import encode_streams, point_count

logger = logging.getLogger(__name__)

SOURCE = DataSource.GARMIN
BACKFILL_CURSOR = "garmin_activities_backfill"
INCREMENTAL_OVERLAP = timedelta(days=7)

_lock = threading.Lock()


class GarminActivitySyncAlreadyRunningError(RuntimeError):
    pass


def is_activity_sync_running() -> bool:
    return _lock.locked()


@dataclass
class GarminSyncLimits:
    per_page: int = 50
    max_backfill_pages: int = 10  # up to 500 older activities per run
    max_details: int = 30  # each one is a separate request: keep Garmin happy


@dataclass
class _Counters:
    created: int = 0
    updated: int = 0


class GarminActivitySyncService:
    def __init__(
        self,
        db: Session,
        api: Callable[[], GarminApi],
        limits: GarminSyncLimits | None = None,
    ) -> None:
        # ``api`` logs in on first call only (see app/services/jobs.py).
        self._db = db
        self._api = api
        self._limits = limits or GarminSyncLimits()

    def run(self, kind: SyncKind = SyncKind.MANUAL) -> SyncLog:
        if not _lock.acquire(blocking=False):
            raise GarminActivitySyncAlreadyRunningError("A Garmin activity sync is running.")
        try:
            return self._run_locked(kind)
        finally:
            _lock.release()

    def _run_locked(self, kind: SyncKind) -> SyncLog:
        log = sync_repo.start_log(self._db, SOURCE, kind)
        counters = _Counters()
        error: str | None
        try:
            self._sync_new_activities(counters)
            self._sync_history(counters)
            self._sync_missing_details()
        except HealthRateLimitedError:
            self._db.commit()  # keep what was imported; the next run continues
            status, error = SyncStatus.PARTIAL, "Garmin rate limit reached; next run continues."
        except HealthProviderError as exc:
            # Expected failure (library broken, login refused): no stack trace.
            self._db.rollback()
            status, error = SyncStatus.FAILED, f"Activities: {exc}"[:500]
        except Exception as exc:
            self._db.rollback()
            logger.exception("Garmin activity sync failed")
            status, error = SyncStatus.FAILED, f"{type(exc).__name__}: {exc}"[:500]
        else:
            status, error = SyncStatus.SUCCESS, None
        # Even after a failure: what was stored before it must be deduplicated.
        reconcile_duplicates(self._db)
        sync_repo.finish_log(self._db, log, status, counters.created, counters.updated, error)
        return log

    def _page(self, offset: int) -> list[dict[str, Any]]:
        items = call_garmin(self._api().get_activities, offset, self._limits.per_page)
        if items is None:
            return []
        if not isinstance(items, list):
            raise HealthProviderError("Garmin activity list has an unexpected format")
        return [item for item in items if isinstance(item, dict)]

    # --- Step 1 -------------------------------------------------------------

    def _sync_new_activities(self, counters: _Counters) -> None:
        latest = activities_repo.latest_start_time(self._db, SOURCE)
        if latest is None:
            return  # first run: the history step starts from the most recent one
        stop_at = latest - INCREMENTAL_OVERLAP
        offset = 0
        while True:
            items = self._page(offset)
            if not items:
                return
            oldest = self._store(items, counters)
            if oldest < stop_at or len(items) < self._limits.per_page:
                return
            offset += len(items)

    # --- Step 2 -------------------------------------------------------------

    def _sync_history(self, counters: _Counters) -> None:
        cursor = sync_repo.get_cursor(self._db, BACKFILL_CURSOR)
        if cursor.completed:
            return
        offset = int(cursor.value or 0)
        for _ in range(self._limits.max_backfill_pages):
            items = self._page(offset)
            if not items:
                cursor.completed = True
                self._db.commit()
                return
            self._store(items, counters)
            offset += len(items)
            cursor.value = str(offset)
            self._db.commit()  # save progress page by page

    # --- Step 3 -------------------------------------------------------------

    def _sync_missing_details(self) -> None:
        activities = activities_repo.activities_missing_streams(
            self._db, SOURCE, self._limits.max_details
        )
        for activity in activities:
            details = call_garmin(
                self._api().get_activity_details, activity.external_id, 2000, 4000
            )
            series = details_to_series(details) if isinstance(details, dict) else {}
            if not series:
                activities_repo.mark_no_streams(self._db, activity)
            else:
                activities_repo.upsert_raw_payload(
                    self._db, SOURCE, "activity_details", activity.external_id, details
                )
                activities_repo.save_stream(
                    self._db, activity, list(series), point_count(series), encode_streams(series)
                )
                activity.summary_polyline = summary_polyline(series) or activity.summary_polyline
            self._db.commit()

    # --- Shared -------------------------------------------------------------

    def _store(self, items: list[dict[str, Any]], counters: _Counters) -> datetime:
        """Upsert a page of summaries; return the oldest start time in it."""
        oldest: datetime | None = None
        for item in items:
            try:
                summary = GarminActivitySummary.model_validate(item)
            except ValidationError:
                logger.warning("Skipping a Garmin activity that failed validation")
                continue
            external_id = str(summary.activity_id)
            activities_repo.upsert_raw_payload(self._db, SOURCE, "activity", external_id, item)
            _, created = activities_repo.upsert_activity(
                self._db, SOURCE, external_id, activity_fields(summary)
            )
            if created:
                counters.created += 1
            else:
                counters.updated += 1
            if oldest is None or summary.start_time_gmt < oldest:
                oldest = summary.start_time_gmt
        self._db.commit()
        if oldest is None:
            raise HealthProviderError("No activity of this Garmin page could be read")
        return oldest
