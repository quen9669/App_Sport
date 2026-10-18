"""Tests for storing health data and the Garmin sync (idempotency, failures)."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DailyHealth, SleepNight
from app.db.models.enums import SyncKind, SyncStatus
from app.integrations.health.garmin_connect import GarminConnectProvider
from app.services.health_sync import run_provider_sync, sync_range
from tests.fixtures.garmin import FakeGarmin

TODAY = date(2026, 10, 18)


def nights(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SleepNight)) or 0


def run(db: Session, fake: FakeGarmin, initial_days: int = 10) -> SyncStatus:
    provider = GarminConnectProvider(login=lambda: fake)
    log = run_provider_sync(db, provider, SyncKind.MANUAL, initial_days, today=lambda: TODAY)
    return SyncStatus(log.status)


def test_sync_range_first_run_and_incremental() -> None:
    assert sync_range(TODAY, None, 90) == (date(2026, 7, 21), TODAY)
    assert sync_range(TODAY, date(2026, 10, 17), 90) == (date(2026, 10, 15), TODAY)


def test_first_sync_imports_initial_window(db: Session) -> None:
    assert run(db, FakeGarmin()) == SyncStatus.SUCCESS

    assert nights(db) == 10
    assert db.scalar(select(func.count()).select_from(DailyHealth)) == 10


def test_resync_creates_no_duplicates_and_fetches_few_days(db: Session) -> None:
    fake = FakeGarmin()
    run(db, fake)
    fake.calls.clear()

    run(db, fake)
    run(db, fake)

    assert nights(db) == 10
    assert len(set(fake.calls)) == 3  # only the last days, with overlap


def test_rate_limit_gives_partial_sync_then_resumes(db: Session) -> None:
    fake = FakeGarmin()
    fake.rate_limit_from = date(2026, 10, 14)

    assert run(db, fake) == SyncStatus.PARTIAL
    assert nights(db) == 5

    fake.rate_limit_from = None
    assert run(db, fake) == SyncStatus.SUCCESS
    assert nights(db) == 10


def test_broken_library_marks_sync_failed_without_crashing(db: Session) -> None:
    fake = FakeGarmin()
    fake.broken = True

    assert run(db, fake) == SyncStatus.FAILED
    assert nights(db) == 0


def test_night_without_sleep_is_skipped(db: Session) -> None:
    fake = FakeGarmin()
    fake.no_sleep_days.add("2026-10-18")

    run(db, fake)

    assert db.scalar(select(SleepNight).where(SleepNight.night_date == TODAY)) is None
