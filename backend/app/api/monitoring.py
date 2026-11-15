"""Monitoring settings page: is the app itself working?

Read-only, technical numbers only (see ``services/monitoring.py``). Signed-in
users only, like every other screen: it is in ``main.PROTECTED_ROUTERS``.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.monitoring import Status, monitoring

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class SourceHealthOut(BaseModel):
    source: str  # "garmin" or "strava"
    status: Status
    last_success_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    last_error: str | None
    failures_7d: int


class BackupHealthOut(BaseModel):
    status: Status
    last_copy_at: datetime | None
    copies: int
    last_copy_bytes: int | None


class MemoryHealthOut(BaseModel):
    status: Status
    used_bytes: int | None  # None outside Docker
    limit_bytes: int | None  # None: no limit set


class CoachHealthOut(BaseModel):
    status: Status
    enabled: bool
    month: str
    spent_eur: float
    limit_eur: float


class MonitoringOut(BaseModel):
    status: Status  # the worst of the checks below
    checked_at: datetime
    started_at: datetime  # when the app (this process) started
    sources: list[SourceHealthOut]
    backup: BackupHealthOut
    memory: MemoryHealthOut
    coach: CoachHealthOut
    database_bytes: int | None
    activities_7d: int
    grafana_url: str | None  # the "Ouvrir dans Grafana" button; None hides it


@router.get("", response_model=MonitoringOut)
def get_monitoring(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> MonitoringOut:
    data = monitoring(db, settings)
    return MonitoringOut(**asdict(data), grafana_url=settings.grafana_url or None)
