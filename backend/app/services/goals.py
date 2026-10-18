"""Weekly goal progress: how much of each goal is done in a given week."""

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, Goal
from app.services.classification import (
    RIDE_SPORTS,
    RUN_SPORTS,
    Category,
    effective_category,
)
from app.services.weeks import Week


class GoalKind(StrEnum):
    STRENGTH_SESSIONS = "strength_sessions"  # number of strength sessions per week
    CARDIO_SESSIONS = "cardio_sessions"  # number of cardio sessions per week
    ACTIVE_MINUTES = "active_minutes"  # minutes of strength + cardio per week
    DISTANCE_KM = "distance_km"  # km per week, optionally only running or cycling


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

    @property
    def achieved(self) -> bool:
        return self.done >= self.goal.target


def activities_in_week(db: Session, week: Week, timezone: str) -> list[Activity]:
    start, end = week.utc_range(timezone)
    query = (
        select(Activity)
        .where(Activity.start_time >= start, Activity.start_time < end)
        .order_by(Activity.start_time)
    )
    return list(db.scalars(query))


def goals_for_week(db: Session, week: Week) -> list[Goal]:
    """Active goals whose dates overlap the week (a goal starting mid-week counts)."""
    query = (
        select(Goal)
        .where(
            Goal.status == GoalStatus.ACTIVE,
            Goal.start_date <= week.sunday,
            (Goal.end_date.is_(None)) | (Goal.end_date >= week.monday),
        )
        .order_by(Goal.id)
    )
    return list(db.scalars(query))


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


def _amount(goal: Goal, activity: Activity) -> float | None:
    """How much one activity adds to a goal, or None if it does not count."""
    category = effective_category(activity)
    if goal.kind in _SESSION_CATEGORY:
        return 1.0 if category == _SESSION_CATEGORY[GoalKind(goal.kind)] else None
    if goal.kind == GoalKind.ACTIVE_MINUTES:
        if category == Category.OTHER:
            return None
        return (activity.moving_time_s or activity.elapsed_time_s) / 60
    if goal.kind == GoalKind.DISTANCE_KM:
        if not activity.distance_m or not _matches_sport(activity, goal.sport):
            return None
        return activity.distance_m / 1000
    return None


def compute_progress(goal: Goal, activities: list[Activity]) -> GoalProgress:
    """Count the activities of the week for one goal.

    Several sessions on the same day each count: two classes on Saturday are
    two sessions.
    """
    progress = GoalProgress(goal=goal, done=0)
    for activity in activities:
        amount = _amount(goal, activity)
        if amount is not None:
            progress.done += amount
            progress.activity_ids.append(activity.id)
    progress.done = round(progress.done, 1)
    return progress


def week_progress(
    db: Session, week: Week, timezone: str
) -> tuple[list[GoalProgress], list[Activity]]:
    """Progress of every active goal for the week, plus the week's activities."""
    activities = activities_in_week(db, week, timezone)
    return [compute_progress(goal, activities) for goal in goals_for_week(db, week)], activities
