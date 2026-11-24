"""Weeks-in-a-row streak and the 30-day calendar of "Ma semaine"."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Activity
from app.db.models.enums import DataSource
from app.repositories import activities as activities_repo
from app.services.activity_calendar import activity_calendar, streak_weeks
from app.services.activity_map import SportGroup
from app.services.weeks import Week

TZ = "Europe/Luxembourg"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)  # Tuesday, week 2026-W48


def add(db: Session, key: str, start: datetime, **fields: Any) -> Activity:
    values: dict[str, Any] = {
        "name": "x",
        "sport_type": "Run",
        "start_time": start,
        "elapsed_time_s": 1800,
        "moving_time_s": 1800,
    }
    values.update(fields)
    activity, _ = activities_repo.upsert_activity(db, DataSource.STRAVA, key, values)
    db.commit()
    return activity


def test_streak_counts_back_and_the_current_week_cannot_break_it() -> None:
    current = Week(2026, 48)
    assert streak_weeks({Week(2026, 47), Week(2026, 46)}, current) == 2  # nothing yet this week
    assert streak_weeks({current, Week(2026, 47), Week(2026, 45)}, current) == 2  # a gap stops it
    assert streak_weeks(set(), current) == 0


def test_calendar_counts_walks_but_not_hidden_or_motorcycle(db: Session) -> None:
    add(db, "walk", datetime(2026, 11, 23, 11, tzinfo=UTC), sport_type="Walk")
    add(db, "hid", datetime(2026, 11, 16, 11, tzinfo=UTC), hidden=True)
    add(db, "moto", datetime(2026, 11, 16, 12, tzinfo=UTC), sport_type="motorcycling_v2")
    add(db, "swim", datetime(2026, 11, 10, 11, tzinfo=UTC), sport_type="Swim")
    calendar = activity_calendar(db, TZ, NOW)
    # W48 (walk) counts, W47 has only a hidden run and a motorcycle trip: the streak stops.
    assert calendar.streak_weeks == 1
    assert [(e.sport, e.day.isoformat()) for e in calendar.entries] == [
        (SportGroup.SWIM, "2026-11-10"),
        (SportGroup.WALK, "2026-11-23"),
    ]
