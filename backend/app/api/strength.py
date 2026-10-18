"""Strength session routes: the exercise catalogue and the sessions typed at the gym."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.db.models import Activity, StrengthSession
from app.db.session import get_db
from app.repositories import strength as strength_repo
from app.services.exercises import CUSTOM_GROUP, EXERCISES

router = APIRouter(prefix="/strength", tags=["strength"])

# Same bounds in frontend/src/utils/bounds.ts.
MAX_SETS = 100


class SetIn(BaseModel):
    exercise: Annotated[str, Field(min_length=1, max_length=64)]
    reps: Annotated[int, Field(ge=1, le=100)]
    weight_kg: Annotated[float, Field(ge=0, le=500)] | None = None
    rpe: Annotated[int, Field(ge=1, le=10)] | None = None

    @field_validator("exercise")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        # " Squat " and "Squat" must be the same exercise: trim and collapse spaces.
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("exercise name is empty")
        return cleaned


class SessionIn(BaseModel):
    performed_at: datetime | None = None  # default: now
    duration_min: Annotated[int, Field(ge=1, le=300)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None
    activity_id: int | None = None
    sets: Annotated[list[SetIn], Field(min_length=1, max_length=MAX_SETS)]

    @field_validator("performed_at")
    @classmethod
    def _aware_and_not_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("performed_at needs a timezone, e.g. 2026-10-18T18:00:00+02:00")
        if value > datetime.now(UTC) + timedelta(hours=1):
            raise ValueError("performed_at cannot be in the future")
        return value.astimezone(UTC)  # stored and returned in UTC, like every datetime


class SetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise: str
    set_number: int
    reps: int
    weight_kg: float | None
    rpe: int | None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    performed_at: datetime
    duration_min: int | None
    notes: str | None
    activity_id: int | None
    sets: list[SetOut]


class ExerciseOut(BaseModel):
    name: str
    group: str
    bodyweight: bool
    # The last set done on this exercise: the default proposed at the gym.
    last_reps: int | None = None
    last_weight_kg: float | None = None


def _check_activity(db: Session, activity_id: int | None, session_id: int | None) -> None:
    """The linked activity must exist and not already be linked to another session."""
    if activity_id is None:
        return
    if db.get(Activity, activity_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown activity")
    linked = strength_repo.session_linked_to(db, activity_id)
    if linked is not None and linked.id != session_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This activity is already linked to another session"
        )


def _sets_fields(sets: list[SetIn]) -> list[dict[str, object]]:
    """Number the sets: position in the session, and 1, 2, 3... per exercise."""
    per_exercise: dict[str, int] = {}
    rows = []
    for position, item in enumerate(sets):
        per_exercise[item.exercise] = per_exercise.get(item.exercise, 0) + 1
        rows.append(
            {
                "position": position,
                "exercise": item.exercise,
                "set_number": per_exercise[item.exercise],
                "reps": item.reps,
                "weight_kg": item.weight_kg,
                "rpe": item.rpe,
            }
        )
    return rows


def _save(db: Session, session: StrengthSession, payload: SessionIn) -> SessionOut:
    _check_activity(db, payload.activity_id, session.id)
    fields = {
        "performed_at": payload.performed_at or datetime.now(UTC),
        "duration_min": payload.duration_min,
        "notes": (payload.notes or "").strip() or None,
        "activity_id": payload.activity_id,
    }
    strength_repo.save_session(db, session, fields, _sets_fields(payload.sets))
    db.commit()
    return SessionOut.model_validate(session)


def _get(db: Session, session_id: int) -> StrengthSession:
    session = strength_repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.get("/exercises", response_model=list[ExerciseOut])
def list_exercises(db: Session = Depends(get_db)) -> list[ExerciseOut]:
    """The catalogue, then the exercises typed freely before, each with its last set."""
    latest = strength_repo.latest_sets_by_exercise(db)
    catalogue = [
        ExerciseOut(name=e.name, group=e.group, bodyweight=e.bodyweight) for e in EXERCISES
    ]
    known = {exercise.name for exercise in catalogue}
    custom = [
        ExerciseOut(name=name, group=CUSTOM_GROUP, bodyweight=False)
        for name in sorted(latest)
        if name not in known
    ]
    result = catalogue + custom
    for exercise in result:
        last = latest.get(exercise.name)
        if last is not None:
            exercise.last_reps = last.reps
            exercise.last_weight_kg = last.weight_kg
    return result


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)
) -> list[SessionOut]:
    return [SessionOut.model_validate(s) for s in strength_repo.list_sessions(db, limit)]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def read_session(session_id: int, db: Session = Depends(get_db)) -> SessionOut:
    return SessionOut.model_validate(_get(db, session_id))


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionIn, db: Session = Depends(get_db)) -> SessionOut:
    return _save(db, StrengthSession(), payload)


@router.put("/sessions/{session_id}", response_model=SessionOut)
def replace_session(
    session_id: int, payload: SessionIn, db: Session = Depends(get_db)
) -> SessionOut:
    """Replace the whole session, sets included (simplest way to edit a typo)."""
    return _save(db, _get(db, session_id), payload)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get(db, session_id))
    db.commit()
