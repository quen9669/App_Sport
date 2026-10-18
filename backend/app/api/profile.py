"""Profile and body measurement routes.

The bounds below are repeated in ``frontend/src/utils/bounds.ts`` so the form
can show errors before sending; the server checks them again because the
browser can never be trusted (anyone can call the API directly).
"""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import profile as profile_repo

router = APIRouter(tags=["profile"])

MIN_AGE, MAX_AGE = 12, 100


def age_on(birth_date: date, today: date) -> int:
    """Age in full years: one less if this year's birthday has not happened yet."""
    before_birthday = (today.month, today.day) < (birth_date.month, birth_date.day)
    return today.year - birth_date.year - int(before_birthday)


class ProfileIn(BaseModel):
    # Annotated[..., Field(ge=, le=)] = "greater or equal" / "less or equal":
    # Pydantic answers 422 with a clear message when a value is out of bounds.
    height_cm: Annotated[float, Field(ge=100, le=250)] | None = None
    sex: Literal["male", "female", "other"] | None = None
    birth_date: date | None = None
    max_heartrate: Annotated[int, Field(ge=120, le=230)] | None = None
    resting_heartrate: Annotated[int, Field(ge=30, le=110)] | None = None
    experience_level: Literal["beginner", "intermediate", "advanced"] | None = None
    injuries: Annotated[str, Field(max_length=2000)] | None = None

    @field_validator("birth_date")
    @classmethod
    def _plausible_age(cls, value: date | None) -> date | None:
        if value is not None and not MIN_AGE <= age_on(value, date.today()) <= MAX_AGE:
            raise ValueError(f"age must be between {MIN_AGE} and {MAX_AGE}")
        return value


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    height_cm: float | None
    sex: str | None
    birth_date: date | None
    max_heartrate: int | None
    resting_heartrate: int | None
    experience_level: str | None
    injuries: str | None
    age: int | None = None  # computed from birth_date, never stored
    updated_at: datetime


class BodyMetricIn(BaseModel):
    measured_on: date
    weight_kg: Annotated[float, Field(ge=30, le=300)]
    body_fat_pct: Annotated[float, Field(ge=3, le=70)] | None = None
    waist_cm: Annotated[float, Field(ge=40, le=200)] | None = None

    @field_validator("measured_on")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        # One day of slack for timezone differences between browser and server.
        if value > date.today() + timedelta(days=1):
            raise ValueError("date cannot be in the future")
        return value


class BodyMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    measured_on: date
    weight_kg: float
    body_fat_pct: float | None
    waist_cm: float | None


def _profile_out(db: Session) -> ProfileOut:
    profile = profile_repo.get_or_create_profile(db)
    out = ProfileOut.model_validate(profile)
    if profile.birth_date is not None:
        out.age = age_on(profile.birth_date, date.today())
    return out


@router.get("/profile", response_model=ProfileOut)
def read_profile(db: Session = Depends(get_db)) -> ProfileOut:
    out = _profile_out(db)
    db.commit()  # the profile row is created on first read
    return out


@router.put("/profile", response_model=ProfileOut)
def save_profile(payload: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    """Replace the whole profile (an empty field clears the stored value)."""
    profile_repo.update_profile(db, payload.model_dump())
    db.commit()
    return _profile_out(db)


@router.get("/body-metrics", response_model=list[BodyMetricOut])
def list_body_metrics(
    days: int | None = Query(default=None, ge=1, le=3660),
    db: Session = Depends(get_db),
) -> list[BodyMetricOut]:
    """Measurements of the last ``days`` days (all of them when omitted)."""
    since = date.today() - timedelta(days=days) if days else None
    return [BodyMetricOut.model_validate(m) for m in profile_repo.list_body_metrics(db, since)]


@router.post("/body-metrics", response_model=BodyMetricOut)
def save_body_metric(payload: BodyMetricIn, db: Session = Depends(get_db)) -> BodyMetricOut:
    fields = payload.model_dump(exclude={"measured_on"})
    metric = profile_repo.upsert_body_metric(db, payload.measured_on, fields)
    db.commit()
    return BodyMetricOut.model_validate(metric)


@router.delete("/body-metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_body_metric(metric_id: int, db: Session = Depends(get_db)) -> None:
    if not profile_repo.delete_body_metric(db, metric_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measurement not found")
    db.commit()
