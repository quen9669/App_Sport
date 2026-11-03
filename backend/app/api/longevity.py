"""Longévité screen: long-term health markers and the smoke-free comparison.

Read-only: everything comes from ``services/longevity.py``. The response is
built from the service's dataclasses, so the shapes below mirror them (and
``frontend/src/api/client.ts`` mirrors these).
"""

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.db.types import utc_now
from app.services.longevity import Evidence, Status, overview

router = APIRouter(prefix="/longevity", tags=["longevity"])


class IndicatorOut(BaseModel):
    key: str
    value: float | None  # None: not enough data yet
    previous: float | None  # one period earlier (4 weeks, 30 days or 3 months)
    unit: str
    status: Status | None  # None: no public reference, or no value
    evidence: Evidence
    samples: int


class ComparisonOut(BaseModel):
    key: str
    unit: str
    before: float | None  # average of the 30 days before the quit date
    after: float | None  # average of the last 30 days (since the quit date at the earliest)
    before_days: int
    after_days: int


class SmokeFreeOut(BaseModel):
    quit_date: date
    days_since_quit: int
    smoke_free_days: int
    current_streak: int
    cigarettes: int
    before_start: date
    before_end: date
    after_start: date
    comparisons: list[ComparisonOut]


class LongevityOut(BaseModel):
    today: date
    indicators: list[IndicatorOut]
    smoke_free: SmokeFreeOut


@router.get("", response_model=LongevityOut)
def read_longevity(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> LongevityOut:
    result = overview(db, settings.app_timezone, utc_now())
    db.commit()  # the profile row is created on first read
    return LongevityOut.model_validate(asdict(result))
