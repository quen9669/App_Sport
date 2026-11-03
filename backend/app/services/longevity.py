"""The Longévité overview: a few long-term health markers, and the smoke-free effect.

Two parts, both read-only and computed from data the app already has:

1. ``indicators``: one number per lever that matters over decades (cardio
   minutes, strength sessions, VO2max, daily steps, sleep, resting heart rate,
   weight). Each has a ``status`` against a public reference when one exists
   (WHO for activity, sleep societies for sleep) and an ``evidence`` level, so
   the screen and the coach can say how solid the link with health is.
2. ``smoke_free``: the counters since the quit date, and a "before / since"
   comparison of the watch's data: the 30 days before the quit date against
   the last 30 days. It shows what changed, not why: training, season and
   stress change these numbers too, and the screen says so.

The French texts live in the interface; here we only produce numbers and
codes (``met``, ``established``...), like the other services.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DailyHealth
from app.repositories import activities as activities_repo
from app.repositories import profile as profile_repo
from app.repositories import smoking as smoking_repo
from app.repositories import strength as strength_repo
from app.services.classification import Category, effective_category
from app.services.health_dashboard import HealthDay, health_days, sleep_regularity, weekly_intensity
from app.services.smoking import DEFAULT_QUIT_DATE, CigaretteDay, summarize
from app.services.strength import counts_on_its_own
from app.services.weeks import Week, local_today, week_of

# Averages need enough days with data, otherwise one good day would look like a habit.
MIN_DAYS = 7
# Windows of the comparisons, in days or weeks.
RECENT_DAYS = 30
WEEKS = 4  # complete weeks: the current one is still in progress
VO2_LOOKBACK_DAYS = 180  # an older VO2max is not "current" any more
VO2_COMPARE_DAYS = 90  # "3 months ago"


class Status(StrEnum):
    """Where a number stands against its public reference."""

    MET = "met"  # the reference is reached
    PARTLY = "partly"  # on the way
    BELOW = "below"  # far from it


class Evidence(StrEnum):
    """How solid the link between this lever and long-term health is."""

    ESTABLISHED = "established"  # large studies and official guidelines agree
    LIKELY = "likely"  # consistent studies, but the dose or the cause is less clear
    UNCERTAIN = "uncertain"  # a useful signal, little proof as a target in itself


@dataclass
class Indicator:
    key: str  # "intensity_minutes", "strength_sessions"... (texts in the interface)
    value: float | None  # None: not enough data
    previous: float | None  # the same measure one period earlier, to show a trend
    unit: str
    status: Status | None  # None: no reference, or no value
    evidence: Evidence
    samples: int  # days, nights or weeks behind ``value``


@dataclass
class Comparison:
    """One measure before the quit date and since."""

    key: str  # "resting_hr", "hrv_ms", "sleep_h", "steps"
    unit: str
    before: float | None
    after: float | None
    before_days: int
    after_days: int


@dataclass
class SmokeFree:
    quit_date: date
    days_since_quit: int
    smoke_free_days: int
    current_streak: int
    cigarettes: int
    # The windows actually compared (the "after" one starts at the quit date at the earliest).
    before_start: date
    before_end: date
    after_start: date
    comparisons: list[Comparison] = field(default_factory=list)


@dataclass
class Overview:
    today: date
    indicators: list[Indicator]
    smoke_free: SmokeFree


# --- small helpers -----------------------------------------------------------


def _average(values: list[float]) -> float | None:
    """Mean of the values, or None when there are fewer than MIN_DAYS of them."""
    if len(values) < MIN_DAYS:
        return None
    return sum(values) / len(values)


def _rounded(value: float | None, digits: int = 0) -> float | None:
    return None if value is None else round(value, digits)


def _present(days: list[HealthDay], pick: Callable[[HealthDay], float | None]) -> list[float]:
    """The values of one measure, skipping the days without it."""
    return [v for v in (pick(d) for d in days) if v is not None]


def _sleep_hours(day: HealthDay) -> float | None:
    return None if day.sleep_s is None else day.sleep_s / 3600


def _band(value: float | None, met: float, partly: float) -> Status | None:
    """Status of a "more is better" measure: met from ``met``, partly from ``partly``."""
    if value is None:
        return None
    if value >= met:
        return Status.MET
    return Status.PARTLY if value >= partly else Status.BELOW


# --- the indicators -----------------------------------------------------------


def _weeks_before(week: Week, count: int) -> list[Week]:
    """The ``count`` weeks before ``week`` (not included), oldest first."""
    weeks = [week.previous()]
    while len(weeks) < count:
        weeks.insert(0, weeks[0].previous())
    return weeks


def intensity_indicator(db: Session, current: Week) -> Indicator:
    """WHO: 150 to 300 moderate minutes per week (a vigorous minute counts double)."""
    # 8 complete weeks: the last 4 are the value, the 4 before the trend.
    by_week = weekly_intensity(db, _weeks_before(current, 2 * WEEKS))
    # A week without any watch data is "unknown", not "zero minutes".
    recent = [w.total for w in by_week[WEEKS:] if w.days > 0]
    older = [w.total for w in by_week[:WEEKS] if w.days > 0]
    value = sum(recent) / len(recent) if recent else None
    return Indicator(
        key="intensity_minutes",
        value=_rounded(value),
        previous=_rounded(sum(older) / len(older)) if older else None,
        unit="min/sem",
        status=_band(value, met=150, partly=75),
        evidence=Evidence.ESTABLISHED,
        samples=len(recent),
    )


def _strength_per_week(db: Session, weeks: list[Week], timezone: str) -> list[int] | None:
    """Strength sessions of each week: watch activities plus sessions typed on their own.

    None when nothing at all was recorded in the period: we can't tell "no
    strength" from "no data" then.
    """
    start, _ = weeks[0].utc_range(timezone)
    _, end = weeks[-1].utc_range(timezone)
    activities = activities_repo.activities_between(db, start, end)
    sessions = strength_repo.sessions_between(db, start, end)
    if not activities and not sessions:
        return None
    moments: list[datetime] = [
        a.start_time
        for a in activities
        if not a.hidden and effective_category(a) == Category.STRENGTH
    ]
    # A typed session already recorded by the watch must not count twice.
    moments += [s.performed_at for s in sessions if counts_on_its_own(s, activities)]
    counts = []
    for week in weeks:
        week_start, week_end = week.utc_range(timezone)
        counts.append(sum(1 for moment in moments if week_start <= moment < week_end))
    return counts


def strength_indicator(db: Session, current: Week, timezone: str) -> Indicator:
    """WHO: muscle strengthening on 2 days or more per week."""
    counts = _strength_per_week(db, _weeks_before(current, 2 * WEEKS), timezone)
    value = sum(counts[WEEKS:]) / WEEKS if counts else None
    return Indicator(
        key="strength_sessions",
        value=_rounded(value, 1),
        previous=_rounded(sum(counts[:WEEKS]) / WEEKS, 1) if counts else None,
        unit="séances/sem",
        status=_band(value, met=2, partly=1),
        evidence=Evidence.ESTABLISHED,
        samples=WEEKS if counts else 0,
    )


def vo2max_indicator(db: Session, today: date) -> Indicator:
    """Garmin's latest VO2max and the one of about 3 months before.

    Fitness is one of the strongest markers of long-term health, but the
    watch's number is an estimate: no status, only the value and its trend.
    """
    rows = db.scalars(
        select(DailyHealth)
        .where(
            DailyHealth.day >= today - timedelta(days=VO2_LOOKBACK_DAYS),
            DailyHealth.day <= today,
            DailyHealth.vo2max.is_not(None),
        )
        .order_by(DailyHealth.day)
    ).all()
    latest = rows[-1] if rows else None
    older = [r for r in rows if r.day <= today - timedelta(days=VO2_COMPARE_DAYS)]
    return Indicator(
        key="vo2max",
        value=latest.vo2max if latest else None,
        previous=older[-1].vo2max if older else None,
        unit="ml/kg/min",
        status=None,
        evidence=Evidence.ESTABLISHED,
        samples=len(rows),
    )


def steps_indicator(recent: list[HealthDay], older: list[HealthDay]) -> Indicator:
    """Studies see the benefit grow up to about 8,000 steps a day (adults under 60)."""
    values = _present(recent, lambda d: d.steps)
    value = _average(values)
    return Indicator(
        key="steps",
        value=_rounded(value),
        previous=_rounded(_average(_present(older, lambda d: d.steps))),
        unit="pas/jour",
        status=_band(value, met=8000, partly=5000),
        evidence=Evidence.LIKELY,
        samples=len(values),
    )


def sleep_indicators(recent: list[HealthDay], older: list[HealthDay]) -> list[Indicator]:
    """Duration (7 to 9 hours for adults) and regularity of the bedtime."""
    hours = _present(recent, _sleep_hours)
    value = _average(hours)
    duration_status = None
    if value is not None:
        if 7 <= value <= 9:
            duration_status = Status.MET
        elif 6 <= value <= 10:
            duration_status = Status.PARTLY
        else:
            duration_status = Status.BELOW
    regularity = sleep_regularity(recent)
    spread = regularity.bedtime_sd_min
    spread_status = None
    if spread is not None:
        spread_status = (
            Status.MET if spread <= 30 else Status.PARTLY if spread <= 60 else Status.BELOW
        )
    return [
        Indicator(
            key="sleep_duration",
            value=_rounded(value, 1),
            previous=_rounded(_average(_present(older, _sleep_hours)), 1),
            unit="h",
            status=duration_status,
            evidence=Evidence.ESTABLISHED,
            samples=len(hours),
        ),
        Indicator(
            key="sleep_regularity",
            value=spread,
            previous=sleep_regularity(older).bedtime_sd_min,
            unit="min",
            status=spread_status,
            evidence=Evidence.LIKELY,
            samples=regularity.nights,
        ),
    ]


def resting_hr_indicator(recent: list[HealthDay], older: list[HealthDay]) -> Indicator:
    """No target: the trend of one's own resting heart rate is what is useful."""
    values = _present(recent, lambda d: d.resting_hr)
    return Indicator(
        key="resting_hr",
        value=_rounded(_average(values)),
        previous=_rounded(_average(_present(older, lambda d: d.resting_hr))),
        unit="bpm",
        status=None,
        evidence=Evidence.LIKELY,
        samples=len(values),
    )


def weight_indicators(db: Session, today: date, timezone: str) -> list[Indicator]:
    """The last weigh-in, the one of 3 months ago, and the BMI when the height is known.

    BMI does not tell muscle from fat: a status, but only "likely" evidence.
    """
    old_day = today - timedelta(days=VO2_COMPARE_DAYS)
    now_point = health_days(db, today, today, timezone)[0]
    old_point = health_days(db, old_day, old_day, timezone)[0]
    weight = now_point.weight_kg
    indicators = [
        Indicator(
            key="weight",
            value=weight,
            previous=old_point.weight_kg,
            unit="kg",
            status=None,
            evidence=Evidence.LIKELY,
            samples=1 if weight is not None else 0,
        )
    ]
    height_cm = profile_repo.get_or_create_profile(db).height_cm
    if height_cm:
        metres = height_cm / 100

        def bmi(kg: float | None) -> float | None:
            return None if kg is None else round(kg / metres**2, 1)

        value = bmi(weight)
        status = None
        if value is not None:
            status = (
                Status.MET
                if 18.5 <= value < 25
                else Status.PARTLY
                if 25 <= value < 30
                else Status.BELOW
            )
        indicators.append(
            Indicator(
                key="bmi",
                value=value,
                previous=bmi(old_point.weight_kg),
                unit="kg/m²",
                status=status,
                evidence=Evidence.LIKELY,
                samples=1 if value is not None else 0,
            )
        )
    return indicators


# --- smoke-free ---------------------------------------------------------------

# The measures compared before / since the quit date: (key, unit, value of a day).
_COMPARED: list[tuple[str, str, Callable[[HealthDay], float | None]]] = [
    ("resting_hr", "bpm", lambda d: d.resting_hr),
    ("hrv_ms", "ms", lambda d: d.hrv_ms),
    ("sleep_h", "h", _sleep_hours),
    ("steps", "pas/jour", lambda d: d.steps),
]


def smoke_free(db: Session, today: date, timezone: str) -> SmokeFree:
    saved = profile_repo.get_or_create_profile(db).smoke_free_since
    quit_date = saved or DEFAULT_QUIT_DATE
    # Notes stay out: the counters are enough here.
    entries = [CigaretteDay(r.day, r.cigarettes) for r in smoking_repo.list_days(db)]
    summary = summarize(quit_date, today, entries)

    before_start = quit_date - timedelta(days=RECENT_DAYS)
    before_end = quit_date - timedelta(days=1)
    # The last 30 days, but never before the quit date (they would mix both periods).
    after_start = max(quit_date, today - timedelta(days=RECENT_DAYS - 1))
    before = health_days(db, before_start, before_end, timezone)
    after = health_days(db, after_start, today, timezone) if after_start <= today else []

    comparisons = []
    for key, unit, pick in _COMPARED:
        before_values, after_values = _present(before, pick), _present(after, pick)
        digits = 1 if key == "sleep_h" else 0
        comparisons.append(
            Comparison(
                key=key,
                unit=unit,
                before=_rounded(_average(before_values), digits),
                after=_rounded(_average(after_values), digits),
                before_days=len(before_values),
                after_days=len(after_values),
            )
        )
    return SmokeFree(
        quit_date=quit_date,
        days_since_quit=summary.days_since_quit,
        smoke_free_days=summary.smoke_free_days,
        current_streak=summary.current_streak,
        cigarettes=summary.cigarettes,
        before_start=before_start,
        before_end=before_end,
        after_start=after_start,
        comparisons=comparisons,
    )


# --- everything ---------------------------------------------------------------


def overview(db: Session, timezone: str, now: datetime) -> Overview:
    """The whole Longévité screen in one call (a few queries, no external API)."""
    today = local_today(timezone, now)
    current = week_of(today)
    # Two windows of 30 days: the last 30 (today included) and the 30 before.
    days = health_days(db, today - timedelta(days=2 * RECENT_DAYS - 1), today, timezone)
    older, recent = days[:RECENT_DAYS], days[RECENT_DAYS:]
    indicators = [
        intensity_indicator(db, current),
        strength_indicator(db, current, timezone),
        vo2max_indicator(db, today),
        steps_indicator(recent, older),
        *sleep_indicators(recent, older),
        resting_hr_indicator(recent, older),
        *weight_indicators(db, today, timezone),
    ]
    return Overview(today, indicators, smoke_free(db, today, timezone))
