"""Tests for the Strava sync, end to end against a fake Strava API.

These tests check the key promise of phase 1: activities land in the database,
and re-running the sync never creates duplicates.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityStream, RawPayload
from app.db.models.enums import SyncStatus
from app.integrations.strava.client import StravaClient
from app.integrations.strava.rate_limit import RateLimiter
from app.repositories import sync as sync_repo
from app.services.strava_sync import BACKFILL_CURSOR, StravaSyncService, SyncLimits
from app.services.stream_codec import decode_streams
from tests.fixtures.strava import BASE_TIME, FakeStravaApi, make_activity, make_history

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def mock_router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


def run_sync(db: Session, limits: SyncLimits | None = None) -> SyncStatus:
    with httpx.Client() as http:
        client = StravaClient(
            http, access_token=lambda: "token", rate_limiter=RateLimiter(sleep=lambda _: None)
        )
        log = StravaSyncService(
            db, client, limits or SyncLimits(per_page=10), now=lambda: NOW
        ).run()
    return SyncStatus(log.status)


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_first_sync_imports_whole_history_and_streams(
    db: Session, mock_router: respx.MockRouter
) -> None:
    api = FakeStravaApi(make_history(25))
    api.install(mock_router)

    assert run_sync(db, SyncLimits(per_page=10, max_streams=50)) == SyncStatus.SUCCESS

    assert count(db, Activity) == 25
    assert sync_repo.get_cursor(db, BACKFILL_CURSOR).completed
    # Gym sessions have no GPS but do have heart rate, so all of them get streams.
    assert count(db, ActivityStream) == 25
    run = db.scalars(select(Activity).where(Activity.sport_type == "Run")).first()
    assert run is not None
    assert run.distance_m == 10_000.0
    assert run.timezone == "Europe/Luxembourg"
    assert run.start_time.tzinfo is not None
    assert run.stream is not None
    assert "heartrate" in decode_streams(run.stream.data)


def test_resync_creates_no_duplicates(db: Session, mock_router: respx.MockRouter) -> None:
    FakeStravaApi(make_history(25)).install(mock_router)

    run_sync(db)
    activities_after_first = count(db, Activity)
    raw_after_first = count(db, RawPayload)
    run_sync(db)
    run_sync(db)

    assert count(db, Activity) == activities_after_first == 25
    assert count(db, RawPayload) == raw_after_first
    logs = sync_repo.list_logs(db)
    assert logs[0].items_created == 0  # last run found nothing new


def test_new_activity_is_picked_up_incrementally(
    db: Session, mock_router: respx.MockRouter
) -> None:
    history = make_history(5)
    api = FakeStravaApi(history)
    api.install(mock_router)
    run_sync(db)

    api.activities.append(make_activity(9999, BASE_TIME + timedelta(days=60)))
    api.calls.clear()
    run_sync(db)

    assert count(db, Activity) == 6
    assert db.scalar(select(Activity).where(Activity.external_id == "9999")) is not None
    # History is complete, so the second run did not page through it again.
    assert api.calls.count("list") <= 2


def test_recent_edit_on_strava_updates_the_same_row(
    db: Session, mock_router: respx.MockRouter
) -> None:
    api = FakeStravaApi(make_history(3))
    api.install(mock_router)
    run_sync(db)

    api.activities[-1]["name"] = "Sortie du dimanche"  # renamed on Strava after upload
    run_sync(db)

    assert count(db, Activity) == 3
    renamed = db.scalars(select(Activity).where(Activity.name == "Sortie du dimanche")).all()
    assert len(renamed) == 1


def test_history_resumes_after_daily_quota(db: Session, mock_router: respx.MockRouter) -> None:
    api = FakeStravaApi(make_history(30))
    api.daily_limit = 8  # allows only a couple of requests (safety margin is 5)
    api.install(mock_router)

    assert run_sync(db) == SyncStatus.PARTIAL
    imported_first = count(db, Activity)
    assert 0 < imported_first < 30
    assert not sync_repo.get_cursor(db, BACKFILL_CURSOR).completed

    # Next day: quota is back, the history import continues where it stopped.
    api.daily_limit, api.daily_usage = 1000, 0
    assert run_sync(db, SyncLimits(per_page=10, max_streams=100)) == SyncStatus.SUCCESS
    assert count(db, Activity) == 30
    assert sync_repo.get_cursor(db, BACKFILL_CURSOR).completed


def test_activity_without_streams_is_not_requested_again(
    db: Session, mock_router: respx.MockRouter
) -> None:
    api = FakeStravaApi([make_activity(1, BASE_TIME)])
    api.streams_without_data.add("1")
    api.install(mock_router)

    run_sync(db)
    api.calls.clear()
    run_sync(db)

    assert "streams:1" not in api.calls


def test_invalid_activity_is_skipped_but_others_imported(
    db: Session, mock_router: respx.MockRouter
) -> None:
    broken = make_activity(2, BASE_TIME + timedelta(days=1))
    broken["elapsed_time"] = "not a number"
    FakeStravaApi([make_activity(1, BASE_TIME), broken]).install(mock_router)

    assert run_sync(db) == SyncStatus.SUCCESS
    assert count(db, Activity) == 1


def test_unreadable_page_marks_run_failed(db: Session, mock_router: respx.MockRouter) -> None:
    broken = make_activity(1, BASE_TIME)
    broken["elapsed_time"] = "not a number"
    FakeStravaApi([broken]).install(mock_router)

    assert run_sync(db) == SyncStatus.FAILED
    assert "format changed" in (sync_repo.list_logs(db)[0].error or "")
