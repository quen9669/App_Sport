"""Synchronise Strava activities into our database.

One run does three things, in this order:

1. **New activities**: everything that started after the most recent
   activity we already have, minus a few days of overlap so that recent
   edits on Strava (renamed activity, corrected sport) are picked up too.
2. **History**: a few more pages of older activities, going back in time from
   where the previous run stopped (stored in ``sync_cursor``), until the very
   first activity is reached. Then the history import is marked complete.
3. **Streams**: the detailed time series of activities that don't have them yet,
   a limited number per run to spare the quota.

Every write is an upsert, so running the sync twice never creates duplicates.
If the daily quota runs out, the run ends as "partial" and the next one simply
continues.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import SyncLog
from app.db.models.enums import DataSource, SyncKind, SyncStatus
from app.db.types import utc_now
from app.integrations.strava.client import MAX_PER_PAGE, StravaClient
from app.integrations.strava.mappers import (
    StravaActivitySummary,
    activity_fields,
    streams_to_series,
)
from app.integrations.strava.rate_limit import DailyLimitReachedError
from app.repositories import activities as activities_repo
from app.repositories import sync as sync_repo
from app.services.stream_codec import encode_streams, point_count

logger = logging.getLogger(__name__)

BACKFILL_CURSOR = "strava_backfill"
# Re-read the last days at each run to catch edits made on Strava after upload.
INCREMENTAL_OVERLAP = timedelta(days=7)
SOURCE = DataSource.STRAVA

# Only one Strava sync at a time, even if the scheduler and a button click collide.
_sync_lock = threading.Lock()


class SyncAlreadyRunningError(RuntimeError):
    """Another Strava sync is in progress."""


def is_sync_running() -> bool:
    return _sync_lock.locked()


@dataclass
class SyncLimits:
    """How much work one run may do. Defaults keep a run within one quota window."""

    max_backfill_pages: int = 5  # 5 x 200 = up to 1,000 older activities per run
    max_streams: int = 40
    per_page: int = MAX_PER_PAGE


@dataclass
class _Counters:
    created: int = 0
    updated: int = 0


class StravaSyncService:
    def __init__(
        self,
        db: Session,
        client: StravaClient,
        limits: SyncLimits | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._db = db
        self._client = client
        self._limits = limits or SyncLimits()
        self._now = now

    def run(self, kind: SyncKind = SyncKind.MANUAL) -> SyncLog:
        """Run one full sync and return its journal entry."""
        if not _sync_lock.acquire(blocking=False):
            raise SyncAlreadyRunningError("A Strava sync is already running.")
        try:
            return self._run_locked(kind)
        finally:
            _sync_lock.release()

    def _run_locked(self, kind: SyncKind) -> SyncLog:
        log = sync_repo.start_log(self._db, SOURCE, kind)
        counters = _Counters()
        try:
            self._sync_new_activities(counters)
            self._sync_history(counters)
            self._sync_missing_streams()
        except DailyLimitReachedError:
            self._db.commit()  # keep everything imported so far
            sync_repo.finish_log(
                self._db,
                log,
                SyncStatus.PARTIAL,
                counters.created,
                counters.updated,
                error="Strava daily quota reached; the next run will continue.",
            )
        except Exception as exc:
            self._db.rollback()
            # Log the type and message only: our log filter also strips any token.
            logger.exception("Strava sync failed")
            sync_repo.finish_log(
                self._db,
                log,
                SyncStatus.FAILED,
                counters.created,
                counters.updated,
                error=f"{type(exc).__name__}: {exc}"[:500],
            )
        else:
            sync_repo.finish_log(
                self._db, log, SyncStatus.SUCCESS, counters.created, counters.updated
            )
        return log

    # --- Step 1 -------------------------------------------------------------

    def _sync_new_activities(self, counters: _Counters) -> None:
        latest = activities_repo.latest_start_time(self._db, SOURCE)
        if latest is None:
            return  # nothing yet: the history step will start from today
        after = int((latest - INCREMENTAL_OVERLAP).timestamp())
        page = 1
        while True:
            items = self._client.list_activities(
                after=after, page=page, per_page=self._limits.per_page
            )
            if not items:
                return
            self._store_activities(items, counters)
            page += 1

    # --- Step 2 -------------------------------------------------------------

    def _sync_history(self, counters: _Counters) -> None:
        cursor = sync_repo.get_cursor(self._db, BACKFILL_CURSOR)
        if cursor.completed:
            return
        # `before` = go back in time from here. First run: from now.
        before = int(cursor.value) if cursor.value else int(self._now().timestamp())
        for _ in range(self._limits.max_backfill_pages):
            items = self._client.list_activities(before=before, per_page=self._limits.per_page)
            if not items:
                cursor.completed = True
                self._db.commit()
                return
            oldest = self._store_activities(items, counters)
            # "+ 1" re-reads activities that share the oldest second (upsert makes it
            # harmless); "min" guarantees we always move backwards and never loop.
            before = min(before - 1, int(oldest.timestamp()) + 1)
            cursor.value = str(before)
            self._db.commit()  # save progress page by page

    # --- Step 3 -------------------------------------------------------------

    def _sync_missing_streams(self) -> None:
        activities = activities_repo.activities_missing_streams(
            self._db, SOURCE, self._limits.max_streams
        )
        for activity in activities:
            payload = self._client.get_activity_streams(activity.external_id)
            series = streams_to_series(payload)
            if not series:
                activities_repo.mark_no_streams(self._db, activity)
            else:
                activities_repo.upsert_raw_payload(
                    self._db, SOURCE, "activity_streams", activity.external_id, payload
                )
                activities_repo.save_stream(
                    self._db, activity, list(series), point_count(series), encode_streams(series)
                )
            self._db.commit()

    # --- Shared -------------------------------------------------------------

    def _store_activities(self, items: list[dict[str, object]], counters: _Counters) -> datetime:
        """Upsert a page of activity summaries; return the oldest start time in it."""
        oldest: datetime | None = None
        for item in items:
            try:
                summary = StravaActivitySummary.model_validate(item)
            except ValidationError:
                # One odd activity must not block the whole sync: keep the raw
                # payload for later analysis and move on.
                logger.warning("Skipping a Strava activity that failed validation")
                continue
            external_id = str(summary.id)
            activities_repo.upsert_raw_payload(self._db, SOURCE, "activity", external_id, item)
            _, created = activities_repo.upsert_activity(
                self._db, SOURCE, external_id, activity_fields(summary)
            )
            if created:
                counters.created += 1
            else:
                counters.updated += 1
            if oldest is None or summary.start_date < oldest:
                oldest = summary.start_date
        self._db.commit()
        if oldest is None:
            # A whole page we cannot read means Strava changed its format: stop
            # loudly (the run is marked "failed") rather than skip data silently.
            raise ValueError("No activity of this Strava page could be read; format changed?")
        return oldest
