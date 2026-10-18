"""Daily health series for the Santé screen: sleep, resting HR, HRV and weight.

The same day can exist in several sources (Garmin, a file import, synthetic
test data). We keep one value per day, from the most trusted source first.
"""

import statistics
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BodyMetric, DailyHealth, SleepNight
from app.db.models.enums import DataSource

# Lower number = preferred when two sources have the same day.
SOURCE_PRIORITY: dict[str, int] = {
    DataSource.GARMIN: 0,
    DataSource.FILE_IMPORT: 1,
    DataSource.SYNTHETIC: 2,
}
# Bedtimes after this hour belong to the evening before (23:30 -> -30 min).
EVENING_FROM_HOUR = 18
MIN_NIGHTS_FOR_REGULARITY = 3


@dataclass
class HealthDay:
    day: date
    sleep_s: int | None = None
    sleep_score: int | None = None
    # Minutes from local midnight: bedtime is negative the evening before
    # (23:30 -> -30, 00:15 -> 15); wake time is positive (07:05 -> 425).
    bedtime_min: int | None = None
    wake_min: int | None = None
    resting_hr: int | None = None
    hrv_ms: float | None = None
    weight_kg: float | None = None


@dataclass
class Regularity:
    """Standard deviation of bed and wake times: low = regular schedule."""

    nights: int
    bedtime_sd_min: int | None
    wake_sd_min: int | None


def _best_by_day[Row: (SleepNight, DailyHealth)](
    rows: Iterable[Row], day_of: Callable[[Row], date]
) -> dict[date, Row]:
    """Keep, for each day, the row of the preferred source."""
    best: dict[date, Row] = {}
    for row in rows:
        day = day_of(row)
        if day not in best or _priority(row.source) < _priority(best[day].source):
            best[day] = row
    return best


def _priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, len(SOURCE_PRIORITY))  # unknown sources last


def minutes_from_midnight(moment: datetime, tz: ZoneInfo, evening_negative: bool) -> int:
    local = moment.astimezone(tz)
    minutes = local.hour * 60 + local.minute
    if evening_negative and local.hour >= EVENING_FROM_HOUR:
        minutes -= 24 * 60
    return minutes


def health_days(db: Session, start: date, end: date, timezone: str) -> list[HealthDay]:
    """One entry per day from ``start`` to ``end`` (both included), oldest first."""
    tz = ZoneInfo(timezone)
    nights = _best_by_day(
        db.scalars(select(SleepNight).where(SleepNight.night_date.between(start, end))),
        lambda night: night.night_date,
    )
    dailies = _best_by_day(
        db.scalars(select(DailyHealth).where(DailyHealth.day.between(start, end))),
        lambda daily: daily.day,
    )
    weights = {
        metric.measured_on: metric.weight_kg
        for metric in db.scalars(
            select(BodyMetric).where(BodyMetric.measured_on.between(start, end))
        )
    }

    result = []
    day = start
    while day <= end:
        point = HealthDay(day=day, weight_kg=weights.get(day))
        night, daily = nights.get(day), dailies.get(day)
        if night is not None:
            point.sleep_s = night.duration_s
            point.sleep_score = night.score
            if night.sleep_start is not None:
                point.bedtime_min = minutes_from_midnight(night.sleep_start, tz, True)
            if night.sleep_end is not None:
                point.wake_min = minutes_from_midnight(night.sleep_end, tz, False)
        # The daily summary first, the night's own values as a fallback.
        point.resting_hr = (daily.resting_heartrate if daily else None) or (
            night.resting_heartrate if night else None
        )
        point.hrv_ms = (daily.hrv_ms if daily else None) or (night.hrv_ms if night else None)
        result.append(point)
        day += timedelta(days=1)
    return result


def sleep_regularity(days: list[HealthDay]) -> Regularity:
    bedtimes = [d.bedtime_min for d in days if d.bedtime_min is not None]
    wakes = [d.wake_min for d in days if d.wake_min is not None]

    def spread(values: list[int]) -> int | None:
        if len(values) < MIN_NIGHTS_FOR_REGULARITY:
            return None  # too few nights to say anything
        return round(statistics.pstdev(values))

    return Regularity(
        nights=len(bedtimes), bedtime_sd_min=spread(bedtimes), wake_sd_min=spread(wakes)
    )
