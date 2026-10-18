"""Store health data from any provider, and run the Garmin synchronisation.

The storing part does not know where data comes from: it receives a
:class:`HealthBatch` and upserts it, so Garmin, file import and synthetic data
all go through the same, tested path.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models import SyncLog
from app.db.models.enums import DataSource, SyncKind, SyncStatus
from app.integrations.health.provider import (
    HealthBatch,
    HealthDataProvider,
    HealthProviderError,
)
from app.repositories import activities as activities_repo
from app.repositories import health as health_repo
from app.repositories import sync as sync_repo

logger = logging.getLogger(__name__)

# Re-read the last days each run: Garmin finalises sleep scores and HRV late.
OVERLAP_DAYS = 2
# Maximum warnings kept in the sync journal, to keep it readable.
_MAX_WARNINGS_IN_LOG = 5

_garmin_lock = threading.Lock()


class HealthSyncAlreadyRunningError(RuntimeError):
    pass


def is_garmin_sync_running() -> bool:
    return _garmin_lock.locked()


@dataclass
class StoreResult:
    created: int = 0
    updated: int = 0
    warnings: list[str] = field(default_factory=list)


def store_batch(db: Session, source: str, batch: HealthBatch) -> StoreResult:
    """Upsert every night and day of ``batch`` (and its raw data), then commit."""
    result = StoreResult(warnings=list(batch.warnings))
    for sleep in batch.sleep:
        created = health_repo.upsert_sleep(db, source, sleep)
        _count(result, created)
        if sleep.raw is not None:
            activities_repo.upsert_raw_payload(
                db, source, "sleep", sleep.night_date.isoformat(), sleep.raw
            )
    for daily in batch.daily:
        created = health_repo.upsert_daily(db, source, daily)
        _count(result, created)
        if daily.raw is not None:
            activities_repo.upsert_raw_payload(
                db, source, "daily_health", daily.day.isoformat(), daily.raw
            )
    db.commit()
    return result


def _count(result: StoreResult, created: bool) -> None:
    if created:
        result.created += 1
    else:
        result.updated += 1


def _summary(warnings: list[str]) -> str | None:
    if not warnings:
        return None
    shown = "; ".join(warnings[:_MAX_WARNINGS_IN_LOG])
    more = len(warnings) - _MAX_WARNINGS_IN_LOG
    return shown + (f" (+{more} more)" if more > 0 else "")


def sync_range(today: date, latest: date | None, initial_days: int) -> tuple[date, date]:
    """Which days to fetch: from the last known day (minus overlap), or the initial window."""
    if latest is None:
        return today - timedelta(days=initial_days - 1), today
    return min(latest - timedelta(days=OVERLAP_DAYS), today), today


def run_provider_sync(
    db: Session,
    provider: HealthDataProvider,
    kind: SyncKind,
    initial_days: int,
    today: Callable[[], date] = date.today,
) -> SyncLog:
    """Fetch from a pull-based provider (Garmin) and store the result, journaled."""
    if not _garmin_lock.acquire(blocking=False):
        raise HealthSyncAlreadyRunningError("A health sync is already running.")
    try:
        log = sync_repo.start_log(db, provider.source, kind)
        latest = health_repo.latest_day(db, provider.source)
        start, end = sync_range(today(), latest, initial_days)
        try:
            batch = provider.fetch_range(start, end)
            result = store_batch(db, provider.source, batch)
        except HealthProviderError as exc:
            db.rollback()
            # Expected failure (library broken, login refused): no stack trace needed.
            sync_repo.finish_log(db, log, SyncStatus.FAILED, 0, 0, error=str(exc)[:500])
            return log
        except Exception as exc:
            db.rollback()
            logger.exception("Health sync failed")
            sync_repo.finish_log(
                db, log, SyncStatus.FAILED, 0, 0, error=f"{type(exc).__name__}: {exc}"[:500]
            )
            return log
        stopped_early = any("rate limit" in w for w in result.warnings)
        sync_repo.finish_log(
            db,
            log,
            SyncStatus.PARTIAL if stopped_early else SyncStatus.SUCCESS,
            result.created,
            result.updated,
            error=_summary(result.warnings),
        )
        return log
    finally:
        _garmin_lock.release()


def import_batch(db: Session, batch: HealthBatch) -> tuple[SyncLog, StoreResult]:
    """Store an uploaded file's content, with a journal entry like any sync."""
    log = sync_repo.start_log(db, DataSource.FILE_IMPORT, SyncKind.MANUAL)
    result = store_batch(db, DataSource.FILE_IMPORT, batch)
    sync_repo.finish_log(
        db, log, SyncStatus.SUCCESS, result.created, result.updated, _summary(result.warnings)
    )
    return log, result
