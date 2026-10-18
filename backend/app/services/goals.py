"""Weekly goal progress: how much of each goal is done in a given week."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, Goal, StrengthSession
from app.repositories import activities as activities_repo
from app.repositories import strength as strength_repo
from app.services.classification import (
    RIDE_SPORTS,
    RUN_SPORTS,
    Category,
    effective_category,
)
from app.services.health_dashboard import weekly_intensity
from app.services.strength import counts_on_its_own
from app.services.training_load import activity_load, heart_rate_params, session_load
from app.services.weeks import Week, local_today

# Load of one activity (TRIMP or estimate), see services/training_load.py.
LoadOf = Callable[[Activity], float]


class GoalKind(StrEnum):
    STRENGTH_SESSIONS = "strength_sessions"  # number of strength sessions per week
    CARDIO_SESSIONS = "cardio_sessions"  # number of cardio sessions per week
    ACTIVE_MINUTES = "active_minutes"  # minutes of strength + cardio per week
    DISTANCE_KM = "distance_km"  # km per week, optionally only running or cycling
    TRAINING_LOAD = "training_load"  # training load points per week (Santé page chart)
    INTENSITY_MINUTES = "intensity_minutes"  # Garmin intensity minutes per week


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"  # kept, but not shown nor counted
    DONE = "done"


class GoalSport(StrEnum):
    RUN = "run"
    RIDE = "ride"


@dataclass
class GoalProgress:
    goal: Goal
    done: float
    activity_ids: list[int] = field(default_factory=list)
    session_ids: list[int] = field(default_factory=list)  # typed strength sessions counted

    @property
    def achieved(self) -> bool:
        return self.done >= self.goal.target


def activities_in_week(db: Session, week: Week, timezone: str) -> list[Activity]:
    start, end = week.utc_range(timezone)
    return activities_repo.activities_between(db, start, end)


def counted_goals(db: Session) -> list[Goal]:
    """Every goal except paused ones.

    "Done" goals stay: they ended, but still count for the weeks they covered
    (history). Note: a goal paused today also disappears from past weeks, as
    the app does not keep the history of status changes.
    """
    query = select(Goal).where(Goal.status != GoalStatus.PAUSED).order_by(Goal.id)
    return list(db.scalars(query))


def overlaps(goal: Goal, week: Week) -> bool:
    """A goal starting or ending mid-week counts for that whole week."""
    return goal.start_date <= week.sunday and (
        goal.end_date is None or goal.end_date >= week.monday
    )


def goals_for_week(db: Session, week: Week) -> list[Goal]:
    return [goal for goal in counted_goals(db) if overlaps(goal, week)]


def _matches_sport(activity: Activity, sport: str | None) -> bool:
    if sport == GoalSport.RUN:
        return activity.sport_type in RUN_SPORTS
    if sport == GoalSport.RIDE:
        return activity.sport_type in RIDE_SPORTS
    return True


# Session goals count one per activity of the right category.
_SESSION_CATEGORY = {
    GoalKind.STRENGTH_SESSIONS: Category.STRENGTH,
    GoalKind.CARDIO_SESSIONS: Category.CARDIO,
}


def _amount(goal: Goal, activity: Activity, load_of: LoadOf | None) -> float | None:
    """How much one activity adds to a goal, or None if it does not count."""
    if goal.kind == GoalKind.TRAINING_LOAD:
        return load_of(activity) if load_of else None
    category = effective_category(activity)
    if goal.kind in _SESSION_CATEGORY:
        return 1.0 if category == _SESSION_CATEGORY[GoalKind(goal.kind)] else None
    if goal.kind == GoalKind.ACTIVE_MINUTES:
        # Walks and short rides (transport) are not sport: no active minutes.
        if category in (Category.OTHER, Category.TRANSPORT):
            return None
        return (activity.moving_time_s or activity.elapsed_time_s) / 60
    if goal.kind == GoalKind.DISTANCE_KM:
        if not activity.distance_m or not _matches_sport(activity, goal.sport):
            return None
        if category == Category.TRANSPORT:  # a trip, not training kilometres
            return None
        return activity.distance_m / 1000
    return None


def _session_amount(goal: Goal, session: StrengthSession) -> float | None:
    """How much one typed strength session (not recorded on Strava) adds to a goal."""
    if goal.kind == GoalKind.STRENGTH_SESSIONS:
        return 1.0
    if goal.kind == GoalKind.ACTIVE_MINUTES:
        return float(session.duration_min or 0)
    if goal.kind == GoalKind.TRAINING_LOAD:
        return session_load(session)
    return None  # no cardio, no distance in a typed strength session


def compute_progress(
    goal: Goal,
    activities: list[Activity],
    sessions: list[StrengthSession] | None = None,
    load_of: LoadOf | None = None,
    intensity: float | None = None,
) -> GoalProgress:
    """Count the activities (and typed strength sessions) of the week for one goal.

    Several sessions on the same day each count: two classes on Saturday are
    two sessions. A typed session already recorded by the watch counts once.
    Hidden activities don't count. ``load_of`` is only needed by training
    load goals: without it, they stay at 0. ``intensity`` is the week's Garmin
    intensity minutes: they come from the watch's daily summary, not from
    activities, so they are passed in already added up.
    """
    progress = GoalProgress(goal=goal, done=0)
    if goal.kind == GoalKind.INTENSITY_MINUTES:
        progress.done = float(intensity or 0)
        return progress
    for activity in activities:
        if activity.hidden:
            continue  # hidden by hand ("Masquer"): never counted
        amount = _amount(goal, activity, load_of)
        if amount is not None:
            progress.done += amount
            progress.activity_ids.append(activity.id)
    for session in sessions or []:
        if not counts_on_its_own(session, activities):
            continue
        amount = _session_amount(goal, session)
        if amount is not None:
            progress.done += amount
            progress.session_ids.append(session.id)
    progress.done = round(progress.done, 1)
    return progress


@dataclass
class WeekData:
    week: Week
    progress: list[GoalProgress]
    activities: list[Activity]
    sessions: list[StrengthSession]

    @property
    def all_achieved(self) -> bool:
        """Every goal of the week reached. A week without any goal is not a success."""
        return bool(self.progress) and all(item.achieved for item in self.progress)


def load_function(db: Session, timezone: str) -> LoadOf:
    """Per-activity load with today's heart rate parameters (looked up once)."""
    params = heart_rate_params(db, local_today(timezone))
    return lambda activity: activity_load(activity, params)[0]


def week_progress(db: Session, week: Week, timezone: str) -> WeekData:
    """Progress of every counted goal for the week, with the week's activities and sessions."""
    start, end = week.utc_range(timezone)
    activities = activities_in_week(db, week, timezone)
    sessions = strength_repo.sessions_between(db, start, end)
    load_of = load_function(db, timezone)
    intensity = weekly_intensity(db, [week])[0].total
    progress = [
        compute_progress(goal, activities, sessions, load_of, intensity)
        for goal in goals_for_week(db, week)
    ]
    return WeekData(week, progress, activities, sessions)


def weeks_history(db: Session, last: Week, count: int, timezone: str) -> list[WeekData]:
    """The ``count`` weeks ending with ``last``, oldest first.

    Everything is loaded with three queries for the whole period, then split by
    week in Python, instead of three queries per week.
    """
    weeks = [last]
    while len(weeks) < count:
        weeks.insert(0, weeks[0].previous())
    start, _ = weeks[0].utc_range(timezone)
    _, end = last.utc_range(timezone)

    activities = activities_repo.activities_between(db, start, end)
    sessions = strength_repo.sessions_between(db, start, end)
    goals = counted_goals(db)
    load_of = load_function(db, timezone)
    intensities = weekly_intensity(db, weeks)

    history = []
    for week, intensity in zip(weeks, intensities, strict=True):
        week_start, week_end = week.utc_range(timezone)
        week_activities = [a for a in activities if week_start <= a.start_time < week_end]
        week_sessions = [s for s in sessions if week_start <= s.performed_at < week_end]
        progress = [
            compute_progress(goal, week_activities, week_sessions, load_of, intensity.total)
            for goal in goals
            if overlaps(goal, week)
        ]
        history.append(WeekData(week, progress, week_activities, week_sessions))
    return history


def streak(history: list[WeekData], current: Week) -> int:
    """Consecutive successful weeks, counting back from the most recent one.

    The current week is still in progress: if it is already a success it
    counts, otherwise it is simply ignored (it can't break the streak yet).
    """
    count = 0
    for data in reversed(history):
        if data.all_achieved:
            count += 1
        elif data.week == current:
            continue
        else:
            break
    return count
