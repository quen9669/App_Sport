"""Week boundaries in Luxembourg time (including DST changes) and category rules."""

from datetime import UTC, date, datetime

import pytest

from app.db.models import Activity
from app.services.classification import Category, automatic_category, effective_category
from app.services.weeks import current_week, parse_week, week_of

TZ = "Europe/Luxembourg"


def test_week_label_and_days() -> None:
    week = parse_week("2026-W42")
    assert week.monday == date(2026, 10, 12)
    assert week.sunday == date(2026, 10, 18)
    assert week.label == "2026-W42"
    assert week.previous().label == "2026-W41"
    assert week.next().label == "2026-W43"
    assert parse_week("2026-W53").next().label == "2027-W01"


def test_iso_year_differs_from_calendar_year() -> None:
    # 1 January 2027 is a Friday: it belongs to the last ISO week of 2026.
    assert week_of(date(2027, 1, 1)).label == "2026-W53"


@pytest.mark.parametrize("label", ["2026-42", "2026-W54", "W42", "2026-W00"])
def test_invalid_week_labels(label: str) -> None:
    with pytest.raises(ValueError):
        parse_week(label)


def test_summer_week_is_utc_plus_two() -> None:
    start, end = parse_week("2026-W42").utc_range(TZ)
    assert start == datetime(2026, 10, 11, 22, 0, tzinfo=UTC)  # Monday 00:00 CEST
    assert end == datetime(2026, 10, 18, 22, 0, tzinfo=UTC)


def test_week_with_end_of_october_dst_change_lasts_169_hours() -> None:
    # Clocks go back on Sunday 25 October 2026: the week has one extra hour.
    start, end = parse_week("2026-W43").utc_range(TZ)
    assert start == datetime(2026, 10, 18, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)
    assert (end - start).total_seconds() == 169 * 3600


def test_week_with_end_of_march_dst_change_lasts_167_hours() -> None:
    # Clocks go forward on Sunday 29 March 2026.
    start, end = parse_week("2026-W13").utc_range(TZ)
    assert (end - start).total_seconds() == 167 * 3600


def test_sunday_late_evening_belongs_to_that_week() -> None:
    # Sunday 18 October 23:30 in Luxembourg = 21:30 UTC: still week 42 locally.
    late_sunday = datetime(2026, 10, 18, 21, 30, tzinfo=UTC)
    assert current_week(TZ, now=late_sunday).label == "2026-W42"
    # ...but 22:30 UTC is already Monday 00:30 locally.
    assert current_week(TZ, now=datetime(2026, 10, 18, 22, 30, tzinfo=UTC)).label == "2026-W43"


@pytest.mark.parametrize(
    ("sport_type", "expected"),
    [
        ("WeightTraining", Category.STRENGTH),
        ("Workout", Category.STRENGTH),  # group class (Body Pump)
        ("Crossfit", Category.STRENGTH),
        ("HighIntensityIntervalTraining", Category.STRENGTH),
        ("Run", Category.CARDIO),
        ("VirtualRide", Category.CARDIO),
        ("Swim", Category.CARDIO),
        ("Yoga", Category.OTHER),
        ("Walk", Category.OTHER),
        ("SomethingNew", Category.OTHER),
    ],
)
def test_automatic_category(sport_type: str, expected: Category) -> None:
    assert automatic_category(sport_type) == expected


def test_manual_override_wins() -> None:
    activity = Activity(sport_type="Workout", category_override="cardio")
    assert effective_category(activity) == Category.CARDIO
    activity.category_override = None
    assert effective_category(activity) == Category.STRENGTH
    activity.category_override = "garbage"
    assert effective_category(activity) == Category.STRENGTH
