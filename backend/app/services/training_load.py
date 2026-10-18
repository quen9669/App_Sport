"""Training load: how hard each session was, added up per week.

**With heart rate**, the load of a session is Banister's **TRIMP** (TRaining
IMPulse): the duration weighted by how high the heart rate was between your
resting and maximum heart rate. The weighting grows exponentially, so 30 min
near your max count much more than 30 min of easy jogging.

    ratio = (average HR - resting HR) / (max HR - resting HR)      (0 to 1)
    TRIMP = minutes x ratio x 0.64 x e^(1.92 x ratio)               (men)
    TRIMP = minutes x ratio x 0.86 x e^(1.67 x ratio)               (women)

**Without heart rate** (or when max/resting HR are unknown), we use the
duration times a rough effort per minute for the kind of session. The factors
are chosen so both methods give similar numbers for typical sessions.

**Acute:chronic ratio (ACWR)**: the load of the last 7 days divided by the
weekly average of the 4 weeks before. Around 0.8-1.3 means "a usual week";
above 1.5 means a sudden increase. It is a coarse indicator, not a diagnosis
of injury risk: the interface says so.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.db.models import Activity, StrengthSession, UserProfile
from app.repositories import activities as activities_repo
from app.repositories import health as health_repo
from app.repositories import profile as profile_repo
from app.repositories import strength as strength_repo
from app.services.classification import Category, effective_category
from app.services.strength import counts_on_its_own
from app.services.weeks import Week

# Effort per minute when there is no heart rate (same scale as TRIMP: an hour
# of easy running at ~65 % of the heart rate reserve is about 85 TRIMP).
EFFORT_PER_MINUTE = {
    Category.CARDIO: 1.4,
    Category.STRENGTH: 0.8,
    Category.OTHER: 0.5,  # walking, yoga...
}
ACUTE_DAYS = 7
CHRONIC_DAYS = 28
# Without a max HR in the profile, the highest one the watch recorded over
# this period is used: it is personal, unlike the 220 - age formula.
OBSERVED_MAX_LOOKBACK = timedelta(days=365)
PLAUSIBLE_MAX_HR = (120, 230)  # same bounds as the profile form


@dataclass
class HeartRateParams:
    """Max and resting heart rate used for TRIMP, and where they come from."""

    max_hr: int | None
    resting_hr: int | None
    sex: str | None
    max_source: str | None = None  # "profile", "observed" or "age"
    resting_source: str | None = None  # "profile" or "garmin"

    @property
    def usable(self) -> bool:
        return (
            self.max_hr is not None
            and self.resting_hr is not None
            and self.max_hr > self.resting_hr
        )


def banister_trimp(
    minutes: float, average_hr: float, max_hr: float, resting_hr: float, sex: str | None
) -> float:
    ratio = (average_hr - resting_hr) / (max_hr - resting_hr)
    ratio = min(max(ratio, 0.0), 1.0)  # a bad reading must not explode the result
    a, b = (0.86, 1.67) if sex == "female" else (0.64, 1.92)
    return minutes * ratio * a * math.exp(b * ratio)


def activity_load(activity: Activity, params: HeartRateParams) -> tuple[float, bool]:
    """Load of one activity and whether it was computed from heart rate."""
    minutes = (activity.moving_time_s or activity.elapsed_time_s) / 60
    if activity.average_heartrate and params.usable:
        assert params.max_hr is not None and params.resting_hr is not None  # for mypy
        trimp = banister_trimp(
            minutes, activity.average_heartrate, params.max_hr, params.resting_hr, params.sex
        )
        return trimp, True
    return minutes * EFFORT_PER_MINUTE[effective_category(activity)], False


def session_load(session: StrengthSession) -> float:
    """A typed strength session (not recorded by the watch): duration x effort."""
    return (session.duration_min or 0) * EFFORT_PER_MINUTE[Category.STRENGTH]


def heart_rate_params(db: Session, today: date) -> HeartRateParams:
    """Max HR: profile, else the highest recorded in a year of activities, else 220 - age.

    Resting HR: profile, else Garmin's recent median.
    """
    profile: UserProfile = profile_repo.get_or_create_profile(db)
    params = HeartRateParams(profile.max_heartrate, profile.resting_heartrate, profile.sex)
    since = datetime.combine(today - OBSERVED_MAX_LOOKBACK, time(), tzinfo=UTC)
    observed = activities_repo.highest_max_heartrate(db, since, *PLAUSIBLE_MAX_HR)
    if params.max_hr is not None:
        params.max_source = "profile"
    elif observed is not None:
        params.max_hr, params.max_source = round(observed), "observed"
    elif profile.birth_date is not None:
        birth = profile.birth_date
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        params.max_hr, params.max_source = 220 - age, "age"
    if params.resting_hr is not None:
        params.resting_source = "profile"
    else:
        recent = health_repo.resting_heartrates_since(db, today - timedelta(days=30))
        if recent:
            params.resting_hr, params.resting_source = round(statistics.median(recent)), "garmin"
    return params


@dataclass
class WeekLoad:
    week: Week
    load: float = 0.0
    sessions: int = 0
    with_heart_rate: int = 0


@dataclass
class LoadSummary:
    weeks: list[WeekLoad]
    params: HeartRateParams
    acute: float = 0.0  # last 7 days
    chronic: float = 0.0  # weekly average of the 4 weeks before
    # False while the history doesn't cover the 4 weeks before: the average
    # would then be too low and the ratio misleadingly high.
    enough_history: bool = False

    @property
    def acwr(self) -> float | None:
        if not self.enough_history or self.chronic <= 0:
            return None
        return round(self.acute / self.chronic, 2)


def training_load(db: Session, last: Week, count: int, timezone: str, now: datetime) -> LoadSummary:
    """Weekly loads of the ``count`` weeks ending with ``last``, and the ACWR at ``now``."""
    weeks = [last]
    while len(weeks) < count:
        weeks.insert(0, weeks[0].previous())
    week_start, _ = weeks[0].utc_range(timezone)
    _, end = last.utc_range(timezone)
    start = min(week_start, now - timedelta(days=ACUTE_DAYS + CHRONIC_DAYS))

    params = heart_rate_params(db, now.date())
    activities = [a for a in activities_repo.activities_between(db, start, end) if not a.hidden]
    sessions = strength_repo.sessions_between(db, start, end)

    # (start time, load, with HR) of everything that counts.
    items: list[tuple[datetime, float, bool]] = []
    for activity in activities:
        load, with_hr = activity_load(activity, params)
        items.append((activity.start_time, load, with_hr))
    for session in sessions:
        if counts_on_its_own(session, activities):
            items.append((session.performed_at, session_load(session), False))

    summary = LoadSummary(weeks=[WeekLoad(week) for week in weeks], params=params)
    ranges = [week.utc_range(timezone) for week in weeks]
    acute_from = now - timedelta(days=ACUTE_DAYS)
    chronic_from = acute_from - timedelta(days=CHRONIC_DAYS)
    # The oldest session must lie in the first week of the chronic window.
    summary.enough_history = any(
        started < chronic_from + timedelta(days=7) for started, _, _ in items
    )
    for started, load, with_hr in items:
        for week_load, (low, high) in zip(summary.weeks, ranges, strict=True):
            if low <= started < high:
                week_load.load += load
                week_load.sessions += 1
                week_load.with_heart_rate += int(with_hr)
        if acute_from <= started <= now:
            summary.acute += load
        elif chronic_from <= started < acute_from:
            summary.chronic += load / (CHRONIC_DAYS / 7)
    for week_load in summary.weeks:
        week_load.load = round(week_load.load)
    summary.acute, summary.chronic = round(summary.acute), round(summary.chronic)
    return summary
