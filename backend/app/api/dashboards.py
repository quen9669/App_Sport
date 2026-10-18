"""Read-only routes for the Santé screen: daily health series and training load."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.db.types import utc_now
from app.services.health_dashboard import health_days, sleep_regularity
from app.services.training_load import training_load
from app.services.weeks import current_week, local_today

router = APIRouter(tags=["dashboards"])


class HealthDayOut(BaseModel):
    day: date
    sleep_s: int | None
    sleep_score: int | None
    bedtime_min: int | None  # minutes from midnight, negative the evening before
    wake_min: int | None
    resting_hr: int | None
    hrv_ms: float | None
    weight_kg: float | None  # last known weight, carried forward
    weight_measured_on: date | None  # when that weight was measured


class RegularityOut(BaseModel):
    nights: int
    bedtime_sd_min: int | None  # standard deviation; None with fewer than 3 nights
    wake_sd_min: int | None


class HealthMetricsOut(BaseModel):
    days: list[HealthDayOut]  # oldest first, one per day (values may be None)
    regularity: RegularityOut


class WeekLoadOut(BaseModel):
    week: str
    monday: date
    load: float
    sessions: int
    with_heart_rate: int  # sessions whose load comes from heart rate (TRIMP)


class HeartRateParamsOut(BaseModel):
    max_hr: int | None
    resting_hr: int | None
    max_source: str | None  # "profile" or "age" (220 - age)
    resting_source: str | None  # "profile" or "garmin"


class TrainingLoadOut(BaseModel):
    weeks: list[WeekLoadOut]  # oldest first, current week last
    acute: float  # load of the last 7 days
    chronic: float  # weekly average of the 4 weeks before
    acwr: float | None  # acute / chronic, None without history
    heart_rate: HeartRateParamsOut


@router.get("/health-metrics", response_model=HealthMetricsOut)
def read_health_metrics(
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthMetricsOut:
    """The last ``days`` days (today included) of sleep, resting HR, HRV and weight."""
    today = local_today(settings.app_timezone)
    series = health_days(db, today - timedelta(days=days - 1), today, settings.app_timezone)
    regularity = sleep_regularity(series)
    return HealthMetricsOut(
        days=[HealthDayOut(**vars(point)) for point in series],
        regularity=RegularityOut(**vars(regularity)),
    )


@router.get("/training-load", response_model=TrainingLoadOut)
def read_training_load(
    weeks: int = Query(default=12, ge=4, le=52),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrainingLoadOut:
    now = utc_now()
    last = current_week(settings.app_timezone, now)
    summary = training_load(db, last, weeks, settings.app_timezone, now)
    params = summary.params
    return TrainingLoadOut(
        weeks=[
            WeekLoadOut(
                week=item.week.label,
                monday=item.week.monday,
                load=item.load,
                sessions=item.sessions,
                with_heart_rate=item.with_heart_rate,
            )
            for item in summary.weeks
        ],
        acute=summary.acute,
        chronic=summary.chronic,
        acwr=summary.acwr,
        heart_rate=HeartRateParamsOut(
            max_hr=params.max_hr,
            resting_hr=params.resting_hr,
            max_source=params.max_source,
            resting_source=params.resting_source,
        ),
    )
