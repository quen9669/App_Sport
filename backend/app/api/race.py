"""Race predictor routes: current form, predicted times, paces and the target race.

Every route answers with the whole screen (``RaceOut``): changing the target or
leaving a run out changes the predictions, and the page simply redraws.
"""

from datetime import date, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Activity
from app.db.session import get_db
from app.db.types import utc_now
from app.repositories import race as race_repo
from app.services.race.efforts import Method, ScoredEffort, Status
from app.services.race.plan import Feasibility
from app.services.race.predictor import RaceReport, race_report

router = APIRouter(prefix="/race", tags=["race"])

# Same bounds in frontend/src/utils/bounds.ts.
DISTANCE_M = (800.0, 100_000.0)
TARGET_TIME_S = (120, 24 * 3600)
ELEVATION_GAIN_M = (0.0, 5000.0)
MAX_DAYS_AHEAD = 2 * 365


# --- Response ------------------------------------------------------------------


class EffortOut(BaseModel):
    activity_id: int
    name: str
    day: date
    distance_m: float
    time_s: float
    vdot: float
    method: Method  # "race" (distance and time) or "heart_rate" (pace and heart rate)
    segment: bool  # the best 5/10 km inside a longer run
    # Heart rate of the whole run (for a segment too: the watch gives no per-km value here).
    average_heartrate: float | None
    max_heartrate: float | None
    weight: float  # 1 today, 0.5 after 45 days...
    used: bool  # part of the estimate (the better half)


class ExcludedRunOut(BaseModel):
    activity_id: int
    name: str
    day: date
    distance_m: float


class FormOut(BaseModel):
    status: Status
    vdot: float | None
    low: float | None
    high: float | None
    reason: str | None  # French, shown as is when the data is insufficient
    efforts: list[EffortOut]
    excluded: list[ExcludedRunOut]


class PredictionOut(BaseModel):
    label: str
    distance_m: float
    time_s: float
    fastest_s: float
    slowest_s: float
    riegel_s: float


class ZoneOut(BaseModel):
    key: str
    slow_s_per_km: float
    fast_s_per_km: float


class SplitOut(BaseModel):
    km: float
    pace_s_per_km: float
    elapsed_s: float


class PacePlanOut(BaseModel):
    target_time_s: float
    average_pace_s_per_km: float
    hill_allowance_s: float
    splits: list[SplitOut]


class FeasibilityOut(BaseModel):
    verdict: Feasibility
    gap_s: float  # target minus prediction: negative = faster than predicted
    gap_pct: float


class TargetOut(BaseModel):
    name: str
    distance_m: float
    race_date: date
    target_time_s: int | None
    elevation_gain_m: float
    days_left: int
    predicted_s: float | None
    required_vdot: float | None
    pace_plan: PacePlanOut | None
    feasibility: FeasibilityOut | None


class RaceOut(BaseModel):
    form: FormOut
    predictions: list[PredictionOut]
    zones: list[ZoneOut]
    target: TargetOut | None


def _effort_out(scored: ScoredEffort, run: Activity) -> EffortOut:
    return EffortOut(
        activity_id=run.id,
        name=run.name,
        day=scored.effort.day,
        distance_m=scored.effort.distance_m,
        time_s=scored.effort.time_s,
        vdot=scored.vdot,
        method=scored.method,
        segment=scored.effort.segment,
        average_heartrate=run.average_heartrate,
        max_heartrate=run.max_heartrate,
        weight=scored.weight,
        used=scored.used,
    )


def _out(report: RaceReport, timezone: str) -> RaceOut:
    form = report.form
    target = None
    if report.target is not None:
        item = report.target
        pacing = item.pace_plan
        target = TargetOut(
            name=item.target.name,
            distance_m=item.target.distance_m,
            race_date=item.target.race_date,
            target_time_s=item.target.target_time_s,
            elevation_gain_m=item.target.elevation_gain_m,
            days_left=item.days_left,
            predicted_s=item.predicted_s,
            required_vdot=item.required_vdot,
            pace_plan=PacePlanOut(
                target_time_s=pacing.target_time_s,
                average_pace_s_per_km=pacing.average_pace_s_per_km,
                hill_allowance_s=pacing.hill_allowance_s,
                splits=[SplitOut(**vars(split)) for split in pacing.splits],
            )
            if pacing is not None
            else None,
            feasibility=FeasibilityOut(**vars(item.feasibility)) if item.feasibility else None,
        )
    return RaceOut(
        form=FormOut(
            status=form.status,
            vdot=form.vdot,
            low=form.low,
            high=form.high,
            reason=form.reason,
            efforts=[
                _effort_out(scored, report.runs[scored.effort.activity_id])
                for scored in form.efforts
            ],
            excluded=[
                ExcludedRunOut(
                    activity_id=run.id,
                    name=run.name,
                    day=run.start_time.astimezone(ZoneInfo(timezone)).date(),
                    distance_m=run.distance_m or 0.0,
                )
                for run in report.excluded
            ],
        ),
        predictions=[PredictionOut(**vars(p)) for p in report.predictions],
        zones=[ZoneOut(**vars(zone)) for zone in report.zones],
        target=target,
    )


def _current(db: Session, settings: Settings) -> RaceOut:
    return _out(race_report(db, settings.app_timezone, utc_now()), settings.app_timezone)


@router.get("", response_model=RaceOut)
def read_race(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> RaceOut:
    return _current(db, settings)


# --- Target race -----------------------------------------------------------------


class TargetIn(BaseModel):
    name: Annotated[str, Field(max_length=120)] = ""
    distance_m: Annotated[float, Field(ge=DISTANCE_M[0], le=DISTANCE_M[1])]
    race_date: date
    target_time_s: Annotated[int, Field(ge=TARGET_TIME_S[0], le=TARGET_TIME_S[1])] | None = None
    elevation_gain_m: Annotated[float, Field(ge=ELEVATION_GAIN_M[0], le=ELEVATION_GAIN_M[1])] = 0.0

    @field_validator("race_date")
    @classmethod
    def _plausible(cls, value: date) -> date:
        # A day of slack for timezones; a race already run can stay a few days.
        today = date.today()
        if value < today - timedelta(days=30) or value > today + timedelta(days=MAX_DAYS_AHEAD):
            raise ValueError("race date must be within the last 30 days or the next 2 years")
        return value


@router.put("/target", response_model=RaceOut)
def save_target(
    payload: TargetIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RaceOut:
    race_repo.save_target(db, payload.model_dump())
    db.commit()
    return _current(db, settings)


@router.delete("/target", response_model=RaceOut)
def delete_target(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> RaceOut:
    race_repo.delete_target(db)
    db.commit()
    return _current(db, settings)


# --- Leaving a run out -------------------------------------------------------------


class ExclusionIn(BaseModel):
    excluded: bool


@router.patch("/efforts/{activity_id}", response_model=RaceOut)
def set_exclusion(
    activity_id: int,
    payload: ExclusionIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RaceOut:
    """Leave a run out of the predictor (or bring it back). Syncs never change it."""
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    activity.excluded_from_race = payload.excluded
    db.commit()
    return _current(db, settings)
