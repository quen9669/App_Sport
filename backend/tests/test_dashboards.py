"""Training load (TRIMP, ACWR) and the daily health series of the Santé screen."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity, BodyMetric, DailyHealth, SleepNight, StrengthSession
from app.db.models.enums import DataSource
from app.repositories import activities as activities_repo
from app.repositories import profile as profile_repo
from app.services.health_dashboard import (
    HealthDay,
    health_days,
    minutes_from_midnight,
    sleep_regularity,
    weekly_intensity,
    weekly_steps,
)
from app.services.training_load import (
    HeartRateParams,
    activity_load,
    banister_trimp,
    heart_rate_params,
    training_load,
)
from app.services.weeks import Week, local_today, week_of

TZ = "Europe/Luxembourg"
NOW = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)  # Sunday evening, week 2026-W42
PARAMS = HeartRateParams(max_hr=190, resting_hr=50, sex="male")


def add_activity(db: Session, external_id: str, start: datetime, **fields: Any) -> Activity:
    values: dict[str, Any] = {
        "name": "x",
        "sport_type": "Run",
        "start_time": start,
        "elapsed_time_s": 3600,
        "moving_time_s": 3600,
    }
    values.update(fields)
    activity, _ = activities_repo.upsert_activity(db, DataSource.STRAVA, external_id, values)
    db.commit()
    return activity


# --- TRIMP -------------------------------------------------------------------


def test_trimp_reference_values() -> None:
    # 60 min at 150 bpm, HR reserve 50-190: ratio 0.714.
    assert banister_trimp(60, 150, 190, 50, "male") == pytest.approx(108.1, abs=0.1)
    assert banister_trimp(60, 150, 190, 50, "female") == pytest.approx(121.5, abs=0.1)
    # At rest the load is zero; a reading above max is capped at ratio 1.
    assert banister_trimp(60, 50, 190, 50, None) == 0
    assert banister_trimp(60, 250, 190, 50, None) == banister_trimp(60, 190, 190, 50, None)


def test_activity_without_heart_rate_uses_estimated_effort(db: Session) -> None:
    run = add_activity(db, "1", NOW, average_heartrate=None)
    gym = add_activity(db, "2", NOW, sport_type="WeightTraining", average_heartrate=None)
    assert activity_load(run, PARAMS) == pytest.approx((84.0, False))
    assert activity_load(gym, PARAMS) == pytest.approx((48.0, False))
    with_hr = add_activity(db, "3", NOW, average_heartrate=150.0)
    load, from_hr = activity_load(with_hr, PARAMS)
    assert from_hr and load == pytest.approx(108.1, abs=0.1)
    # Unknown max HR: no TRIMP possible, fall back to the estimate.
    no_max = HeartRateParams(None, 50, None)
    assert activity_load(with_hr, no_max) == pytest.approx((84.0, False))


def test_heart_rate_params_fall_back_to_age_and_garmin(db: Session) -> None:
    profile = profile_repo.get_or_create_profile(db)
    profile.birth_date = date(1990, 11, 1)  # 35 on 2026-10-18
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 17), resting_heartrate=48))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 16), resting_heartrate=52))
    db.commit()
    params = heart_rate_params(db, date(2026, 10, 18))
    assert (params.max_hr, params.max_source) == (185, "age")
    assert (params.resting_hr, params.resting_source) == (50, "garmin")

    profile.max_heartrate, profile.resting_heartrate = 192, 47
    db.commit()
    params = heart_rate_params(db, date(2026, 10, 18))
    assert (params.max_hr, params.resting_hr) == (192, 47)
    assert params.max_source == params.resting_source == "profile"


def test_max_hr_falls_back_to_the_highest_recorded(db: Session) -> None:
    """No max HR in the profile: the watch's highest reading beats 220 - age."""
    profile = profile_repo.get_or_create_profile(db)
    profile.birth_date = date(1990, 11, 1)
    add_activity(db, "1", NOW - timedelta(days=10), max_heartrate=181.0)
    add_activity(db, "2", NOW - timedelta(days=20), max_heartrate=187.4)
    add_activity(db, "3", NOW - timedelta(days=30), max_heartrate=250.0)  # glitch
    add_activity(db, "4", NOW - timedelta(days=40), max_heartrate=199.0, hidden=True)
    add_activity(db, "5", NOW - timedelta(days=400), max_heartrate=195.0)  # too old
    params = heart_rate_params(db, NOW.date())
    assert (params.max_hr, params.max_source) == (187, "observed")

    profile.max_heartrate = 190
    db.commit()
    assert heart_rate_params(db, NOW.date()).max_source == "profile"


def test_weekly_load_and_acwr(db: Session) -> None:
    # 4 easy weeks (one 60-min run without HR = 84 each), then a big last week.
    for week_back in range(1, 5):
        add_activity(db, f"w{week_back}", NOW - timedelta(days=7 * week_back + 1))
    add_activity(db, "a1", NOW - timedelta(days=1))
    add_activity(db, "a2", NOW - timedelta(days=2))
    add_activity(db, "hidden", NOW - timedelta(days=3), hidden=True)  # never counted
    db.add(StrengthSession(performed_at=NOW - timedelta(days=4), duration_min=50))
    db.commit()

    summary = training_load(db, week_of(NOW.date()), 6, TZ, NOW)

    assert [w.week.label for w in summary.weeks][-1] == "2026-W42"
    assert summary.weeks[-1].load == 84 * 2 + 40  # 2 runs + typed session (50 x 0.8)
    assert summary.weeks[-1].sessions == 3
    assert summary.weeks[-2].load == 84
    assert summary.acute == 208
    assert summary.chronic == 84
    assert summary.acwr == pytest.approx(2.48)


def test_no_history_means_no_acwr(db: Session) -> None:
    summary = training_load(db, week_of(NOW.date()), 4, TZ, NOW)
    assert summary.acwr is None
    assert all(week.load == 0 for week in summary.weeks)


def test_short_history_gives_no_misleading_acwr(db: Session) -> None:
    # Only 2 weeks of data: the 4-week average would be half of the real one.
    add_activity(db, "old", NOW - timedelta(days=12))
    add_activity(db, "new", NOW - timedelta(days=1))
    summary = training_load(db, week_of(NOW.date()), 4, TZ, NOW)
    assert summary.chronic == 21
    assert summary.acwr is None


# --- Health series ----------------------------------------------------------------


def test_bedtime_is_negative_the_evening_before() -> None:
    tz = ZoneInfo(TZ)
    # 21:30 UTC = 23:30 in Luxembourg (summer time).
    assert minutes_from_midnight(datetime(2026, 7, 1, 21, 30, tzinfo=UTC), tz, True) == -30
    assert minutes_from_midnight(datetime(2026, 7, 1, 22, 15, tzinfo=UTC), tz, True) == 15
    assert minutes_from_midnight(datetime(2026, 7, 2, 5, 5, tzinfo=UTC), tz, False) == 425


def test_sleep_regularity() -> None:
    regular = [HealthDay(date(2026, 10, d), bedtime_min=-30, wake_min=420) for d in range(1, 8)]
    assert sleep_regularity(regular).bedtime_sd_min == 0
    irregular = [
        HealthDay(date(2026, 10, 1), bedtime_min=-90, wake_min=360),
        HealthDay(date(2026, 10, 2), bedtime_min=30, wake_min=480),
        HealthDay(date(2026, 10, 3), bedtime_min=-30, wake_min=420),
    ]
    result = sleep_regularity(irregular)
    assert result.nights == 3
    assert result.bedtime_sd_min == 49
    assert result.wake_sd_min == 49
    assert sleep_regularity(irregular[:2]).bedtime_sd_min is None  # too few nights


def test_health_days_prefer_garmin_and_fill_gaps(db: Session) -> None:
    day = date(2026, 10, 17)
    db.add(SleepNight(source="synthetic", night_date=day, duration_s=1000))
    db.add(
        SleepNight(
            source="garmin",
            night_date=day,
            duration_s=27000,
            score=80,
            sleep_start=datetime(2026, 10, 16, 21, 30, tzinfo=UTC),
            sleep_end=datetime(2026, 10, 17, 5, 0, tzinfo=UTC),
            resting_heartrate=51,
            hrv_ms=60.0,
        )
    )
    db.add(BodyMetric(measured_on=day, weight_kg=75.5))
    db.commit()

    days = health_days(db, date(2026, 10, 16), day, TZ)

    assert [d.day for d in days] == [date(2026, 10, 16), day]
    assert days[0].sleep_s is None  # no data that night: an empty point
    last = days[1]
    assert (last.sleep_s, last.sleep_score) == (27000, 80)
    assert (last.bedtime_min, last.wake_min) == (-30, 420)
    assert (last.resting_hr, last.hrv_ms, last.weight_kg) == (51, 60.0, 75.5)


def test_dashboard_routes(client: TestClient) -> None:
    metrics = client.get("/api/health-metrics?days=7").json()
    assert len(metrics["days"]) == 7
    assert metrics["regularity"]["nights"] == 0
    load = client.get("/api/training-load").json()
    assert len(load["weeks"]) == 12
    assert load["acwr"] is None
    assert load["heart_rate"]["max_hr"] is None
    assert load["target"] is None  # no training load goal
    assert client.get("/api/health-metrics?days=3").status_code == 422


def test_weekly_intensity_counts_vigorous_minutes_twice(db: Session) -> None:
    w41, w42 = Week(2026, 41), Week(2026, 42)
    # Monday and Sunday of week 42, and the Sunday before (week 41).
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 12), intensity_moderate_min=30))
    db.add(
        DailyHealth(
            source="garmin",
            day=date(2026, 10, 18),
            intensity_moderate_min=20,
            intensity_vigorous_min=40,
        )
    )
    # Same day from a synthetic source: Garmin wins, it is not added twice.
    db.add(DailyHealth(source="synthetic", day=date(2026, 10, 18), intensity_moderate_min=500))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 11), intensity_vigorous_min=10))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 13), resting_heartrate=50))  # no data
    db.commit()

    before, current = weekly_intensity(db, [w41, w42])

    assert (before.total, before.days) == (20, 1)
    assert (current.moderate, current.vigorous, current.days) == (50, 40, 2)
    assert current.total == 50 + 2 * 40


def test_intensity_minutes_route_and_goal(client: TestClient, db: Session) -> None:
    body = client.get("/api/intensity-minutes").json()
    assert len(body["weeks"]) == 12
    assert body["target"] is None

    today = week_of(local_today(TZ)).monday
    db.add(
        DailyHealth(
            source="garmin", day=today, intensity_moderate_min=100, intensity_vigorous_min=50
        )
    )
    db.commit()
    goal = client.post("/api/goals", json={"kind": "intensity_minutes", "target": 350}).json()

    body = client.get("/api/intensity-minutes").json()
    assert body["target"] == 350
    assert body["weeks"][-1]["total"] == 200
    progress = client.get("/api/goals/progress").json()
    item = next(i for i in progress["goals"] if i["goal"]["id"] == goal["id"])
    assert item["done"] == 200


def test_weekly_steps_average_only_days_with_data(db: Session) -> None:
    w42 = Week(2026, 42)
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 12), steps=8000, floors_ascended=10))
    db.add(
        DailyHealth(
            source="garmin",
            day=date(2026, 10, 13),
            steps=12000,
            floors_ascended=4,
            floors_descended=6,
        )
    )
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 14), resting_heartrate=50))  # no data
    db.commit()

    (week,) = weekly_steps(db, [w42])

    assert (week.steps, week.step_days, week.steps_per_day) == (20000, 2, 10000)
    assert (week.floors_ascended, week.floors_descended, week.floor_days) == (14, 6, 2)
    assert weekly_steps(db, [Week(2026, 40)])[0].steps_per_day is None


def test_steps_floors_route_and_goals(client: TestClient, db: Session) -> None:
    body = client.get("/api/steps-floors").json()
    assert len(body["weeks"]) == 12
    assert (body["steps_target"], body["floors_target"]) == (None, None)

    monday = week_of(local_today(TZ)).monday
    db.add(DailyHealth(source="garmin", day=monday, steps=9000, floors_ascended=20))
    db.commit()
    steps = client.post("/api/goals", json={"kind": "steps", "target": 10000}).json()
    floors = client.post("/api/goals", json={"kind": "floors", "target": 50}).json()
    assert client.post("/api/goals", json={"kind": "steps", "target": 500}).status_code == 422

    body = client.get("/api/steps-floors").json()
    assert (body["steps_target"], body["floors_target"]) == (10000, 50)
    assert body["weeks"][-1]["steps_per_day"] == 9000
    progress = {
        i["goal"]["id"]: i["done"] for i in client.get("/api/goals/progress").json()["goals"]
    }
    assert (progress[steps["id"]], progress[floors["id"]]) == (9000, 20)
    day = client.get("/api/health-metrics?days=7").json()["days"]
    assert any(d["steps"] == 9000 and d["floors_ascended"] == 20 for d in day)
