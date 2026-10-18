"""Weekly goal routes and the week's progress (used by the home dashboard)."""

from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.rows import ActivityRowFields, row_fields
from app.config import Settings, get_settings
from app.db.models import Goal
from app.db.session import get_db
from app.repositories import goals as goals_repo
from app.services.activity_location import Locator
from app.services.classification import activity_automatic_category, effective_category
from app.services.dedupe import DuplicateStatus
from app.services.goals import (
    GoalKind,
    GoalSport,
    GoalStatus,
    streak,
    week_progress,
    weeks_history,
)
from app.services.strength import counts_on_its_own
from app.services.weeks import current_week, parse_week

router = APIRouter(prefix="/goals", tags=["goals"])

# Allowed targets per kind (also in frontend/src/utils/bounds.ts).
TARGET_BOUNDS: dict[GoalKind, tuple[float, float]] = {
    GoalKind.STRENGTH_SESSIONS: (1, 14),
    GoalKind.CARDIO_SESSIONS: (1, 14),
    GoalKind.ACTIVE_MINUTES: (10, 3000),
    GoalKind.DISTANCE_KM: (1, 1000),
    GoalKind.TRAINING_LOAD: (10, 5000),
    GoalKind.INTENSITY_MINUTES: (10, 3000),
}


def _check_goal(kind: GoalKind, target: float, sport: GoalSport | None) -> None:
    low, high = TARGET_BOUNDS[kind]
    if not low <= target <= high:
        raise ValueError(f"target for {kind} must be between {low:g} and {high:g}")
    if sport is not None and kind != GoalKind.DISTANCE_KM:
        raise ValueError("sport only applies to distance goals")


class GoalIn(BaseModel):
    kind: GoalKind
    target: Annotated[float, Field(gt=0)]
    sport: GoalSport | None = None
    start_date: date | None = None  # default: today
    end_date: date | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        # mode="after": runs once every field is parsed, so fields can be compared.
        _check_goal(self.kind, self.target, self.sport)
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class GoalPatch(BaseModel):
    """Only the fields sent are changed."""

    target: Annotated[float, Field(gt=0)] | None = None
    status: GoalStatus | None = None
    end_date: date | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    target: float
    sport: str | None
    start_date: date
    end_date: date | None
    status: str


class GoalProgressOut(BaseModel):
    goal: GoalOut
    done: float
    achieved: bool
    activity_ids: list[int]
    session_ids: list[int]  # typed strength sessions counted on their own


class WeekActivityOut(ActivityRowFields):
    sport_type: str
    category: str  # what is counted
    automatic_category: str  # what the rule says, to show "corrected by hand"
    source: str  # "garmin", "strava"...
    hidden: bool  # hidden by hand: listed greyed out, never counted
    # Maybe the same session as another activity of the list (see services/dedupe.py).
    possible_duplicate: bool


class WeekSessionOut(BaseModel):
    id: int
    performed_at: datetime
    duration_min: int | None
    exercises: list[str]  # names, in the order they were done
    set_count: int
    # False when the same session was recorded on Strava: it is counted through
    # that activity instead (no double counting).
    counted: bool


class WeekProgressOut(BaseModel):
    week: str
    previous_week: str
    next_week: str
    monday: date
    sunday: date
    goals: list[GoalProgressOut]
    activities: list[WeekActivityOut]
    sessions: list[WeekSessionOut]


class HistoryGoalOut(BaseModel):
    goal_id: int
    kind: str
    sport: str | None
    target: float
    done: float
    achieved: bool


class HistoryWeekOut(BaseModel):
    week: str
    monday: date
    goals: list[HistoryGoalOut]
    all_achieved: bool


class HistoryOut(BaseModel):
    weeks: list[HistoryWeekOut]  # oldest first
    streak: int  # consecutive weeks where every goal was reached


def _get_goal(db: Session, goal_id: int) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    return goal


@router.get("", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db)) -> list[GoalOut]:
    return [GoalOut.model_validate(goal) for goal in goals_repo.list_goals(db)]


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalIn, db: Session = Depends(get_db)) -> GoalOut:
    fields = payload.model_dump()
    fields["start_date"] = payload.start_date or date.today()
    goal = goals_repo.create_goal(db, fields)
    db.commit()
    return GoalOut.model_validate(goal)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, payload: GoalPatch, db: Session = Depends(get_db)) -> GoalOut:
    goal = _get_goal(db, goal_id)
    # exclude_unset: ignore the fields the client did not send.
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("status") is None:
        fields.pop("status", None)
    if fields.get("target") is not None:
        try:
            sport = GoalSport(goal.sport) if goal.sport else None
            _check_goal(GoalKind(goal.kind), fields["target"], sport)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    else:
        fields.pop("target", None)
    goals_repo.update_goal(db, goal, fields)
    db.commit()
    return GoalOut.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_goal(db, goal_id))
    db.commit()


@router.get("/progress", response_model=WeekProgressOut)
def read_progress(
    week: str | None = Query(default=None, description="ISO week, e.g. 2026-W42"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WeekProgressOut:
    """Progress of the active goals for one week (the current week by default)."""
    try:
        selected = parse_week(week) if week else current_week(settings.app_timezone)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    data = week_progress(db, selected, settings.app_timezone)
    locator = Locator(db)
    return WeekProgressOut(
        week=selected.label,
        previous_week=selected.previous().label,
        next_week=selected.next().label,
        monday=selected.monday,
        sunday=selected.sunday,
        goals=[
            GoalProgressOut(
                goal=GoalOut.model_validate(item.goal),
                done=item.done,
                achieved=item.achieved,
                activity_ids=item.activity_ids,
                session_ids=item.session_ids,
            )
            for item in data.progress
        ],
        activities=[
            WeekActivityOut(
                **row_fields(a, locator.locate(a)),
                sport_type=a.sport_type,
                category=effective_category(a),
                automatic_category=activity_automatic_category(a),
                source=a.source,
                hidden=a.hidden,
                possible_duplicate=a.duplicate_status == DuplicateStatus.POSSIBLE,
            )
            for a in data.activities
        ],
        sessions=[
            WeekSessionOut(
                id=session.id,
                performed_at=session.performed_at,
                duration_min=session.duration_min,
                # dict.fromkeys keeps the first occurrence of each name, in order.
                exercises=list(dict.fromkeys(s.exercise for s in session.sets)),
                set_count=len(session.sets),
                counted=counts_on_its_own(session, data.activities),
            )
            for session in data.sessions
        ],
    )


@router.get("/history", response_model=HistoryOut)
def read_history(
    weeks: int = Query(default=12, ge=1, le=52),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HistoryOut:
    """The last ``weeks`` weeks (current one included) and the streak of successful weeks.

    The streak is computed over up to a year, even when fewer weeks are shown.
    """
    current = current_week(settings.app_timezone)
    history = weeks_history(db, current, max(weeks, 52), settings.app_timezone)
    return HistoryOut(
        weeks=[
            HistoryWeekOut(
                week=data.week.label,
                monday=data.week.monday,
                goals=[
                    HistoryGoalOut(
                        goal_id=item.goal.id,
                        kind=item.goal.kind,
                        sport=item.goal.sport,
                        target=item.goal.target,
                        done=item.done,
                        achieved=item.achieved,
                    )
                    for item in data.progress
                ],
                all_achieved=data.all_achieved,
            )
            for data in history[-weeks:]
        ],
        streak=streak(history, current),
    )
