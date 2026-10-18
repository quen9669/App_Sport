"""Garmin activities: mapping, sync (against a fake Garmin) and duplicates with Strava."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Activity, ActivityStream, Goal, SleepNight, StrengthSession, SyncLog
from app.db.models.enums import DataSource, SyncStatus
from app.integrations.health.garmin_activities import (
    GarminActivitySummary,
    activity_fields,
    details_to_series,
    summary_polyline,
)
from app.integrations.strava.mappers import garmin_id_from_external_id
from app.repositories import activities as activities_repo
from app.repositories import sync as sync_repo
from app.services import jobs
from app.services.classification import Category, automatic_category
from app.services.dedupe import DuplicateStatus, reconcile_duplicates
from app.services.garmin_activity_sync import (
    BACKFILL_CURSOR,
    GarminActivitySyncService,
    GarminSyncLimits,
)
from app.services.goals import compute_progress
from app.services.stream_codec import decode_streams
from app.services.strength import counts_on_its_own
from tests.fixtures.garmin import FakeGarmin, activity_details, garmin_activity

START = datetime(2026, 10, 12, 6, 30, tzinfo=UTC)


def run(db: Session, api: FakeGarmin, **limits: Any) -> SyncStatus:
    service = GarminActivitySyncService(db, lambda: api, GarminSyncLimits(per_page=5, **limits))
    return SyncStatus(service.run().status)


def history(count: int) -> list[dict[str, Any]]:
    """``count`` Garmin activities, one every 2 days, alternating run / gym."""
    return [
        garmin_activity(
            1000 + i,
            START - timedelta(days=2 * i),
            "running" if i % 2 == 0 else "strength_training",
            distance_m=10_000.0 if i % 2 == 0 else 0.0,
        )
        for i in range(count)
    ]


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def add(db: Session, source: str, external_id: str, start: datetime, **fields: Any) -> Activity:
    values: dict[str, Any] = {
        "name": "x",
        "sport_type": "Run" if source == DataSource.STRAVA else "running",
        "start_time": start,
        "elapsed_time_s": 3600,
    }
    values.update(fields)
    activity, _ = activities_repo.upsert_activity(db, source, external_id, values)
    db.commit()
    return activity


# --- Mapping -------------------------------------------------------------------


def test_summary_mapping_uses_gmt_time_and_si_units() -> None:
    fields = activity_fields(
        GarminActivitySummary.model_validate(garmin_activity(42, START, "indoor_cycling"))
    )
    # startTimeLocal is 2 h later: it must not be used.
    assert fields["start_time"] == START
    assert fields["sport_type"] == "indoor_cycling"
    assert fields["is_trainer"] is True
    assert fields["elapsed_time_s"] == 3660
    assert fields["average_heartrate"] == 142.0
    assert fields["has_heartrate"] is True
    assert fields["garmin_activity_id"] == "42"


def test_zero_distance_of_a_gym_session_becomes_none() -> None:
    item = garmin_activity(1, START, "strength_training", distance_m=0.0)
    assert activity_fields(GarminActivitySummary.model_validate(item))["distance_m"] is None


def test_details_become_aligned_series() -> None:
    series = details_to_series(activity_details(START, samples=3))
    assert series["time"] == [0, 5, 10]
    assert series["heartrate"] == [120.0, 121.0, 122.0]
    assert series["altitude"] == [300.0, 301.0, 302.0]
    assert series["latlng"][0] == [49.61, 6.13]
    assert summary_polyline(series)


def test_details_without_gps_have_no_route() -> None:
    series = details_to_series(activity_details(START, gps=False))
    assert "latlng" not in series
    assert summary_polyline(series) is None
    assert details_to_series({}) == {}


@pytest.mark.parametrize(
    ("type_key", "category"),
    [
        ("running", Category.CARDIO),
        ("indoor_cycling", Category.CARDIO),
        ("strength_training", Category.STRENGTH),
        ("hiit", Category.STRENGTH),
        ("indoor_cardio", Category.STRENGTH),  # gym classes, like Strava "Workout"
        ("yoga", Category.OTHER),
        ("walking", Category.OTHER),
    ],
)
def test_garmin_types_are_classified(type_key: str, category: Category) -> None:
    assert automatic_category(type_key) == category


@pytest.mark.parametrize(
    ("external_id", "expected"),
    [
        ("garmin_ping_123456789", "123456789"),
        ("garmin_push_987", "987"),
        ("my_ride.fit", None),
        (None, None),
    ],
)
def test_garmin_id_is_read_from_strava_external_id(
    external_id: str | None, expected: str | None
) -> None:
    assert garmin_id_from_external_id(external_id) == expected


# --- Sync ------------------------------------------------------------------------


def test_first_sync_imports_history_and_details(db: Session) -> None:
    api = FakeGarmin(history(12))

    assert run(db, api, max_details=20) == SyncStatus.SUCCESS

    assert count(db, Activity) == 12
    assert sync_repo.get_cursor(db, BACKFILL_CURSOR).completed
    assert count(db, ActivityStream) == 12  # every one has heart rate
    newest = db.scalar(select(Activity).where(Activity.external_id == "1000"))
    assert newest is not None and newest.stream is not None
    assert newest.summary_polyline  # route built from the GPS samples
    assert "heartrate" in decode_streams(newest.stream.data)


def test_resync_is_idempotent_and_picks_up_new_activities(db: Session) -> None:
    api = FakeGarmin(history(8))
    run(db, api)
    run(db, api)
    assert count(db, Activity) == 8

    api.activities.insert(0, garmin_activity(2000, START + timedelta(days=1)))
    run(db, api)
    assert count(db, Activity) == 9


def test_history_is_imported_over_several_runs(db: Session) -> None:
    api = FakeGarmin(history(12))
    run(db, api, max_backfill_pages=1)  # 5 per page, 1 page per run
    assert count(db, Activity) == 5
    assert not sync_repo.get_cursor(db, BACKFILL_CURSOR).completed
    run(db, api, max_backfill_pages=1)
    run(db, api, max_backfill_pages=1)
    run(db, api, max_backfill_pages=1)  # the empty page marks the end
    assert count(db, Activity) == 12
    assert sync_repo.get_cursor(db, BACKFILL_CURSOR).completed


def test_rate_limit_keeps_activities_and_ends_partial(db: Session) -> None:
    api = FakeGarmin(history(3))
    api.rate_limit_details = True
    assert run(db, api) == SyncStatus.PARTIAL
    assert count(db, Activity) == 3


def test_broken_library_fails_cleanly(db: Session) -> None:
    api = FakeGarmin(history(3))
    api.broken = True
    assert run(db, api) == SyncStatus.FAILED
    assert count(db, Activity) == 0


# --- Duplicates with Strava ---------------------------------------------------------


def test_strava_copy_with_garmin_id_is_confirmed(db: Session) -> None:
    garmin = add(db, DataSource.GARMIN, "555", START, garmin_activity_id="555")
    # Different start time on purpose: the id alone is enough.
    strava = add(db, DataSource.STRAVA, "9", START + timedelta(hours=1), garmin_activity_id="555")

    reconcile_duplicates(db)

    assert strava.duplicate_status == DuplicateStatus.CONFIRMED
    assert strava.duplicate_of_id == garmin.id
    week = activities_repo.activities_between(db, START - timedelta(days=1), START + timedelta(1))
    assert [a.id for a in week] == [garmin.id]


def test_same_time_and_duration_is_a_duplicate(db: Session) -> None:
    garmin = add(db, DataSource.GARMIN, "1", START)
    strava = add(db, DataSource.STRAVA, "9", START + timedelta(minutes=2), elapsed_time_s=3300)

    reconcile_duplicates(db)

    assert strava.duplicate_status == DuplicateStatus.CONFIRMED
    assert strava.duplicate_of_id == garmin.id


def test_two_candidates_stay_visible_as_possible_duplicates(db: Session) -> None:
    # Two Garmin recordings 6 minutes apart (e.g. stopped and restarted the watch).
    add(db, DataSource.GARMIN, "1", START)
    closest = add(db, DataSource.GARMIN, "2", START + timedelta(minutes=6))
    strava = add(db, DataSource.STRAVA, "9", START + timedelta(minutes=5))

    reconcile_duplicates(db)

    assert strava.duplicate_status == DuplicateStatus.POSSIBLE
    assert strava.duplicate_of_id == closest.id
    window = activities_repo.activities_between(db, START - timedelta(1), START + timedelta(1))
    assert strava in window  # still visible: the user decides


def test_strava_only_activity_is_kept(db: Session) -> None:
    add(db, DataSource.GARMIN, "1", START)
    # Indoor ride sent straight to Strava, the same evening.
    indoor = add(db, DataSource.STRAVA, "9", START + timedelta(hours=11), sport_type="VirtualRide")
    # Same start but a very different duration: not the same session.
    other = add(db, DataSource.STRAVA, "10", START + timedelta(minutes=3), elapsed_time_s=1200)

    reconcile_duplicates(db)

    assert indoor.duplicate_status is None
    assert other.duplicate_status is None


def test_timezone_offset_does_not_hide_a_duplicate(db: Session) -> None:
    """Both sources are compared in UTC: a local-time mix-up would be 1-2 h off."""
    api = FakeGarmin([garmin_activity(77, START)])
    run(db, api)
    strava = add(db, DataSource.STRAVA, "9", START)

    reconcile_duplicates(db)

    assert strava.duplicate_status == DuplicateStatus.CONFIRMED


def test_category_and_strength_link_follow_the_kept_activity(db: Session) -> None:
    strava = add(
        db, DataSource.STRAVA, "9", START, sport_type="Workout", category_override="cardio"
    )
    session = StrengthSession(performed_at=START, activity_id=strava.id)
    db.add(session)
    db.commit()
    garmin = add(db, DataSource.GARMIN, "1", START, sport_type="indoor_cardio")

    reconcile_duplicates(db)

    assert garmin.category_override == "cardio"
    assert session.activity_id == garmin.id


def test_hidden_activity_is_not_counted(db: Session) -> None:
    goal = Goal(kind="cardio_sessions", target=2, start_date=START.date())
    visible = add(db, DataSource.STRAVA, "1", START)
    hidden = add(db, DataSource.STRAVA, "2", START + timedelta(days=1), hidden=True)

    progress = compute_progress(goal, [visible, hidden])

    assert progress.done == 1
    assert progress.activity_ids == [visible.id]


def test_session_linked_to_hidden_activity_counts_on_its_own(db: Session) -> None:
    hidden = add(db, DataSource.STRAVA, "1", START, sport_type="WeightTraining", hidden=True)
    session = StrengthSession(performed_at=START, activity_id=hidden.id)
    assert counts_on_its_own(session, [hidden])


def test_garmin_job_syncs_health_then_activities_with_one_login(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    api = FakeGarmin(history(2))
    logins: list[bool] = []

    def fake_login(*_args: str) -> FakeGarmin:
        logins.append(True)
        return api

    monkeypatch.setattr(jobs, "login_with_library", fake_login)
    log = jobs.run_garmin_sync(session_factory, login=jobs.garmin_login_once(get_settings()))

    assert log.status == SyncStatus.SUCCESS
    assert logins == [True]  # health and activities shared the same client
    with session_factory() as db:
        assert count(db, Activity) == 2
        assert count(db, SleepNight) > 0
        assert count(db, SyncLog) == 2  # one journal entry for each part
