"""Smoke-free tracking routes: counters, days with a cigarette, quit date.

Health data like the rest: it stays in the local database and is never sent
anywhere (the coaches will only get the counters, if FRANKS wants it later).
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.repositories import profile as profile_repo
from app.repositories import smoking as smoking_repo
from app.services.smoking import DEFAULT_QUIT_DATE, CigaretteDay, summarize
from app.services.weeks import local_today

router = APIRouter(prefix="/smoking", tags=["smoking"])

# Same bounds in frontend/src/utils/bounds.ts.
MAX_CIGARETTES_PER_DAY = 60
EARLIEST_DATE = date(2000, 1, 1)


def _not_in_future(value: date) -> date:
    # One day of slack for timezone differences between browser and server.
    if value > date.today() + timedelta(days=1):
        raise ValueError("date cannot be in the future")
    if value < EARLIEST_DATE:
        raise ValueError(f"date cannot be before {EARLIEST_DATE.isoformat()}")
    return value


class CigaretteDayIn(BaseModel):
    cigarettes: Annotated[int, Field(ge=1, le=MAX_CIGARETTES_PER_DAY)]
    note: Annotated[str, Field(max_length=500)] | None = None


class CigaretteDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    cigarettes: int
    note: str | None


class QuitDateIn(BaseModel):
    quit_date: date

    @field_validator("quit_date")
    @classmethod
    def _plausible(cls, value: date) -> date:
        return _not_in_future(value)


class MonthOut(BaseModel):
    month: str
    days: int
    smoke_free_days: int
    cigarettes: int


class SmokingOut(BaseModel):
    quit_date: date
    quit_date_is_default: bool  # not saved yet: the app's default date
    today: date
    days_since_quit: int
    smoke_free_days: int
    cigarette_days: int
    cigarettes: int
    current_streak: int
    longest_streak: int
    months: list[MonthOut]
    entries: list[CigaretteDayOut]  # every day with a cigarette, newest first


def _summary(db: Session, settings: Settings) -> SmokingOut:
    saved = profile_repo.get_or_create_profile(db).smoke_free_since
    quit_date = saved or DEFAULT_QUIT_DATE
    rows = smoking_repo.list_days(db)
    summary = summarize(
        quit_date,
        local_today(settings.app_timezone),
        [CigaretteDay(r.day, r.cigarettes, r.note) for r in rows],
    )
    return SmokingOut(
        quit_date=summary.quit_date,
        quit_date_is_default=saved is None,
        today=summary.today,
        days_since_quit=summary.days_since_quit,
        smoke_free_days=summary.smoke_free_days,
        cigarette_days=summary.cigarette_days,
        cigarettes=summary.cigarettes,
        current_streak=summary.current_streak,
        longest_streak=summary.longest_streak,
        months=[MonthOut(**vars(m)) for m in summary.months],
        entries=[CigaretteDayOut.model_validate(r) for r in reversed(rows)],
    )


@router.get("", response_model=SmokingOut)
def read_smoking(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> SmokingOut:
    out = _summary(db, settings)
    db.commit()  # the profile row is created on first read
    return out


@router.put("/days/{day}", response_model=SmokingOut)
def save_cigarette_day(
    day: date,
    payload: CigaretteDayIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SmokingOut:
    """Write (or correct) the number of cigarettes of one day."""
    try:
        _not_in_future(day)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    note = payload.note.strip() if payload.note else None
    smoking_repo.upsert_day(db, day, payload.cigarettes, note or None)
    db.commit()
    return _summary(db, settings)


@router.delete("/days/{day}", response_model=SmokingOut)
def delete_cigarette_day(
    day: date, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> SmokingOut:
    """Remove a day written by mistake: it becomes smoke-free again."""
    if not smoking_repo.delete_day(db, day):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cigarette on that day")
    db.commit()
    return _summary(db, settings)


@router.put("/quit-date", response_model=SmokingOut)
def save_quit_date(
    payload: QuitDateIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SmokingOut:
    profile_repo.update_profile(db, {"smoke_free_since": payload.quit_date})
    db.commit()
    return _summary(db, settings)
