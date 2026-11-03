"""Longévité screen: markers against public references, and before / since quitting."""

import json
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.coach.tools import ALL_TOOLS, ToolContext, run_tool, tools_for
from app.config import get_settings
from app.db.models import BodyMetric, DailyHealth, SleepNight, StrengthSession
from app.repositories import profile as profile_repo
from app.services.longevity import Evidence, Indicator, Status, overview
from tests.test_dashboards import add_activity

TZ = "Europe/Luxembourg"
NOW = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)  # Sunday evening, week 2026-W42
TODAY = date(2026, 10, 18)
# The 8 complete weeks before W42: W34 (17 Aug) to W41 (5-11 Oct).
RECENT_MONDAY = date(2026, 9, 14)  # W38, first of the last 4 complete weeks
OLDER_MONDAY = date(2026, 8, 17)  # W34


def by_key(indicators: list[Indicator]) -> dict[str, Indicator]:
    return {indicator.key: indicator for indicator in indicators}


def days(start: date, count: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(count)]


def test_empty_database_gives_no_number_and_no_verdict(db: Session) -> None:
    result = overview(db, TZ, NOW)
    assert result.today == TODAY
    for indicator in result.indicators:
        assert indicator.value is None and indicator.status is None, indicator.key
    assert "bmi" not in by_key(result.indicators)  # no height in the profile
    smoke = result.smoke_free
    assert smoke.quit_date == date(2026, 9, 1)  # the app's default
    assert smoke.days_since_quit == smoke.current_streak == 48
    assert all(c.before is None and c.after is None for c in smoke.comparisons)


def test_intensity_minutes_average_the_last_four_complete_weeks(db: Session) -> None:
    for day in days(RECENT_MONDAY, 28):  # 30 moderate min a day = 210 per week
        db.add(DailyHealth(source="garmin", day=day, intensity_moderate_min=30))
    for day in days(OLDER_MONDAY, 28):  # 5 vigorous min a day = 70 per week
        db.add(DailyHealth(source="garmin", day=day, intensity_vigorous_min=5))
    # The current week does not count yet, however big it is.
    db.add(DailyHealth(source="garmin", day=TODAY, intensity_vigorous_min=500))
    db.commit()
    intensity = by_key(overview(db, TZ, NOW).indicators)["intensity_minutes"]
    assert (intensity.value, intensity.previous, intensity.samples) == (210, 70, 4)
    assert intensity.status == Status.MET
    assert intensity.evidence == Evidence.ESTABLISHED


def test_strength_counts_watch_sessions_and_typed_ones_only_once(db: Session) -> None:
    for week in range(4):
        monday = RECENT_MONDAY + timedelta(weeks=week)
        for day in (0, 3):  # Monday and Thursday at 18:00 UTC
            start = datetime.combine(monday + timedelta(days=day), datetime.min.time(), UTC)
            add_activity(db, f"s{week}{day}", start.replace(hour=18), sport_type="WeightTraining")
    # Typed 1 h after a watch session: the same session, not counted again.
    db.add(StrengthSession(performed_at=datetime(2026, 10, 5, 19, 0, tzinfo=UTC)))
    # Typed alone, without the watch: counted.
    db.add(StrengthSession(performed_at=datetime(2026, 10, 10, 10, 0, tzinfo=UTC)))
    db.commit()
    strength = by_key(overview(db, TZ, NOW).indicators)["strength_sessions"]
    assert strength.value == 2.2  # (8 + 1) / 4, rounded
    assert strength.previous == 0  # data exists, no session in the weeks before
    assert strength.status == Status.MET


def test_sleep_steps_heart_rate_and_their_status(db: Session) -> None:
    for offset, day in enumerate(days(TODAY - timedelta(days=29), 30)):
        start = datetime.combine(day, datetime.min.time(), UTC) - timedelta(hours=1)
        # Bedtime alternating 23:00 and 00:00 local: a 30 min spread.
        start += timedelta(hours=offset % 2)
        db.add(
            SleepNight(
                source="garmin", night_date=day, duration_s=int(6.5 * 3600), sleep_start=start
            )
        )
        db.add(DailyHealth(source="garmin", day=day, steps=9000, resting_heartrate=52))
    db.commit()
    result = by_key(overview(db, TZ, NOW).indicators)
    assert (result["sleep_duration"].value, result["sleep_duration"].status) == (
        6.5,
        Status.PARTLY,
    )
    assert result["sleep_regularity"].value == 30
    assert result["sleep_regularity"].status == Status.MET
    assert (result["steps"].value, result["steps"].status) == (9000, Status.MET)
    assert result["resting_hr"].value == 52
    assert result["resting_hr"].status is None  # a trend, not a target
    assert result["resting_hr"].previous is None  # no data in the 30 days before


def test_vo2max_latest_and_three_months_before(db: Session) -> None:
    db.add(DailyHealth(source="garmin", day=date(2026, 6, 1), vo2max=44))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 15), vo2max=47))
    db.add(DailyHealth(source="garmin", day=date(2025, 1, 1), vo2max=30))  # too old
    db.commit()
    vo2 = by_key(overview(db, TZ, NOW).indicators)["vo2max"]
    assert (vo2.value, vo2.previous, vo2.samples) == (47, 44, 2)


def test_weight_and_bmi_with_the_height(db: Session) -> None:
    profile_repo.get_or_create_profile(db).height_cm = 180
    db.add(BodyMetric(measured_on=date(2026, 6, 1), weight_kg=84, source="manual"))
    db.add(BodyMetric(measured_on=date(2026, 10, 1), weight_kg=81, source="manual"))
    db.commit()
    result = by_key(overview(db, TZ, NOW).indicators)
    assert (result["weight"].value, result["weight"].previous) == (81, 84)
    assert result["bmi"].value == 25.0  # 81 / 1.8²
    assert result["bmi"].status == Status.PARTLY
    assert result["bmi"].previous == 25.9


def test_before_and_since_quitting(db: Session) -> None:
    quit_date = date(2026, 9, 1)
    for day in days(quit_date - timedelta(days=30), 30):  # August: before
        db.add(DailyHealth(source="garmin", day=day, resting_heartrate=60, hrv_ms=40))
    for day in days(TODAY - timedelta(days=29), 30):  # the last 30 days
        db.add(DailyHealth(source="garmin", day=day, resting_heartrate=55, hrv_ms=46))
    # Early September: since quitting, but outside the last 30 days.
    db.add(DailyHealth(source="garmin", day=date(2026, 9, 5), resting_heartrate=90))
    db.commit()
    smoke = overview(db, TZ, NOW).smoke_free
    assert (smoke.before_start, smoke.before_end) == (date(2026, 8, 2), date(2026, 8, 31))
    assert smoke.after_start == date(2026, 9, 19)
    compared = {c.key: c for c in smoke.comparisons}
    assert (compared["resting_hr"].before, compared["resting_hr"].after) == (60, 55)
    assert (compared["hrv_ms"].before, compared["hrv_ms"].after) == (40, 46)
    assert compared["resting_hr"].after_days == 30
    assert compared["steps"].before is None  # no steps recorded


def test_recent_quit_compares_only_the_days_since(db: Session) -> None:
    quit_date = TODAY - timedelta(days=9)
    profile_repo.get_or_create_profile(db).smoke_free_since = quit_date
    for day in days(quit_date - timedelta(days=20), 30):  # 20 days before, 10 since
        db.add(DailyHealth(source="garmin", day=day, steps=6000 if day < quit_date else 8000))
    db.commit()
    smoke = overview(db, TZ, NOW).smoke_free
    assert smoke.after_start == quit_date
    steps = next(c for c in smoke.comparisons if c.key == "steps")
    assert (steps.before, steps.after, steps.after_days) == (6000, 8000, 10)


def test_route_and_coach_tool(client: TestClient, db: Session) -> None:
    body = client.get("/api/longevity").json()
    assert {i["key"] for i in body["indicators"]} >= {"intensity_minutes", "vo2max", "steps"}
    assert body["smoke_free"]["quit_date"] == "2026-09-01"
    assert len(body["smoke_free"]["comparisons"]) == 4

    assert "get_longevity_overview" in {t.name for t in tools_for("longevity")}
    assert "get_longevity_overview" not in {t.name for t in tools_for("training")}
    context = ToolContext(db, get_settings(), "longevity", NOW)
    text, is_error = run_tool(ALL_TOOLS["get_longevity_overview"], context, {})
    result = json.loads(text)
    assert not is_error
    assert result["smoke_free"]["days_since_quit"] == 48
    assert "not its cause" in result["note"]
