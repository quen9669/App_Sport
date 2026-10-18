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
from app.services.weeks import Week

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
    # The last known weight: weigh-ins are rare, so a value is carried forward
    # until the next one. ``weight_measured_on`` says when it was measured.
    weight_kg: float | None = None
    weight_measured_on: date | None = None


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
    weights = _weights_carried_forward(db, start, end)

    result = []
    day = start
    while day <= end:
        point = HealthDay(day=day)
        if day in weights:
            point.weight_measured_on, point.weight_kg = weights[day]
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


def _weights_carried_forward(db: Session, start: date, end: date) -> dict[date, tuple[date, float]]:
    """For each day, the last weigh-in on or before it: ``{day: (measured_on, kg)}``.

    The weigh-in just before ``start`` is included, so a period without any
    new weigh-in still shows the last known weight instead of nothing.
    """
    previous = db.scalar(
        select(BodyMetric)
        .where(BodyMetric.measured_on < start)
        .order_by(BodyMetric.measured_on.desc())
        .limit(1)
    )
    in_range = db.scalars(
        select(BodyMetric)
        .where(BodyMetric.measured_on.between(start, end))
        .order_by(BodyMetric.measured_on)
    )
    measured = {m.measured_on: m.weight_kg for m in ([previous] if previous else [])}
    measured.update({m.measured_on: m.weight_kg for m in in_range})

    result: dict[date, tuple[date, float]] = {}
    last: tuple[date, float] | None = None
    day = min([start, *measured])
    while day <= end:
        if day in measured:
            last = (day, measured[day])
        if last is not None and day >= start:
            result[day] = last
        day += timedelta(days=1)
    return result


@dataclass
class WeekIntensity:
    """Garmin intensity minutes of one week, counted like Garmin does."""

    week: Week
    moderate: int = 0
    vigorous: int = 0
    days: int = 0  # days with data: 0 means "no data", not "no effort"

    @property
    def total(self) -> int:
        # Garmin's rule (WHO recommendation): a vigorous minute counts double.
        return self.moderate + 2 * self.vigorous


def weekly_intensity(db: Session, weeks: list[Week]) -> list[WeekIntensity]:
    """Intensity minutes of each week in ``weeks`` (one query for all of them)."""
    if not weeks:
        return []
    rows = db.scalars(
        select(DailyHealth).where(DailyHealth.day.between(weeks[0].monday, weeks[-1].sunday))
    )
    by_day = _best_by_day(
        (
            r
            for r in rows
            if r.intensity_moderate_min is not None or r.intensity_vigorous_min is not None
        ),
        lambda daily: daily.day,
    )
    result = []
    for week in weeks:
        item = WeekIntensity(week)
        for day, daily in by_day.items():
            if week.monday <= day <= week.sunday:
                item.moderate += daily.intensity_moderate_min or 0
                item.vigorous += daily.intensity_vigorous_min or 0
                item.days += 1
        result.append(item)
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
