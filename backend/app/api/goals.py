"""Weekly goal routes and the week's progress (used by the home dashboard)."""

from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Goal
from app.db.session import get_db
from app.repositories import goals as goals_repo
from app.services.classification import automatic_category, effective_category
from app.services.goals import GoalKind, GoalSport, GoalStatus, week_progress
from app.services.weeks import current_week, parse_week

router = APIRouter(prefix="/goals", tags=["goals"])

# Allowed targets per kind (also in frontend/src/utils/bounds.ts).
TARGET_BOUNDS: dict[GoalKind, tuple[float, float]] = {
    GoalKind.STRENGTH_SESSIONS: (1, 14),
    GoalKind.CARDIO_SESSIONS: (1, 14),
    GoalKind.ACTIVE_MINUTES: (10, 3000),
    GoalKind.DISTANCE_KM: (1, 1000),
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


class WeekActivityOut(BaseModel):
    id: int
    name: str
    sport_type: str
    start_time: datetime
    moving_time_s: int | None
    elapsed_time_s: int
    distance_m: float | None
    category: str  # what is counted
    automatic_category: str  # what the rule says, to show "corrected by hand"


class WeekProgressOut(BaseModel):
    week: str
    previous_week: str
    next_week: str
    monday: date
    sunday: date
    goals: list[GoalProgressOut]
    activities: list[WeekActivityOut]


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

    progress, activities = week_progress(db, selected, settings.app_timezone)
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
            )
            for item in progress
        ],
        activities=[
            WeekActivityOut(
                id=a.id,
                name=a.name,
                sport_type=a.sport_type,
                start_time=a.start_time,
                moving_time_s=a.moving_time_s,
                elapsed_time_s=a.elapsed_time_s,
                distance_m=a.distance_m,
                category=effective_category(a),
                automatic_category=automatic_category(a.sport_type),
            )
            for a in activities
        ],
    )
