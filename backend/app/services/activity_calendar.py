"""Weekly streak and the last 30 days of activities (the "Ma semaine" calendar).

A week "counts" when it holds at least one activity, whatever the sport. Hidden
activities never count (FRANKS hid them on purpose); walks count (they are in his
calendar), but the other trips (motorcycle, short rides) are not sport.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import Activity
from app.repositories import activities as activities_repo
from app.services.activity_map import SportGroup, sport_group
from app.services.classification import Category, effective_category
from app.services.weeks import Week, local_today, week_of

# How far back the streak is searched (a streak of 5 years is more than enough).
STREAK_LOOKBACK_DAYS = 5 * 366
# The dot table shows this many days back from today.
RECENT_DAYS = 30


@dataclass
class CalendarEntry:
    activity: Activity
    day: date  # local day
    sport: SportGroup


@dataclass
class ActivityCalendar:
    streak_weeks: int
    today: date
    monday: date  # Monday of the current week
    entries: list[CalendarEntry]  # from the earlier of (30 days ago, this Monday), oldest first


def counts_as_sport(activity: Activity) -> bool:
    if activity.hidden:
        return False
    return sport_group(activity) == SportGroup.WALK or (
        effective_category(activity) != Category.TRANSPORT
    )


def streak_weeks(active_weeks: set[Week], current: Week) -> int:
    """Consecutive weeks with an activity. The current week can't break it yet."""
    week = current if current in active_weeks else current.previous()
    count = 0
    while week in active_weeks:
        count += 1
        week = week.previous()
    return count


def activity_calendar(db: Session, timezone: str, now: datetime | None = None) -> ActivityCalendar:
    moment = now or datetime.now(UTC)
    today = local_today(timezone, moment)
    zone = ZoneInfo(timezone)
    start = moment - timedelta(days=STREAK_LOOKBACK_DAYS)
    entries = [
        CalendarEntry(a, a.start_time.astimezone(zone).date(), sport_group(a))
        for a in activities_repo.activities_between(db, start, moment + timedelta(days=1))
        if counts_as_sport(a)
    ]
    current = week_of(today)
    streak = streak_weeks({week_of(e.day) for e in entries}, current)
    since = min(today - timedelta(days=RECENT_DAYS - 1), current.monday)
    return ActivityCalendar(streak, today, current.monday, [e for e in entries if e.day >= since])
