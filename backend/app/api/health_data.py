"""Health data routes: Garmin status and file import (plan B)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models.enums import DataSource
from app.db.session import get_db
from app.integrations.health.file_import import parse_file
from app.integrations.health.provider import HealthProviderError
from app.repositories import activities as activities_repo
from app.repositories import health as health_repo
from app.repositories import sync as sync_repo
from app.services.garmin_activity_sync import BACKFILL_CURSOR
from app.services.health_sync import import_batch
from app.services.jobs import is_garmin_configured

router = APIRouter(tags=["health data"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB is plenty for years of daily rows


class GarminStatus(BaseModel):
    configured: bool
    night_count: int
    day_count: int
    latest_day: date | None
    activity_count: int
    activity_history_complete: bool


class ImportResult(BaseModel):
    nights: int
    days: int
    created: int
    updated: int
    warnings: list[str]


@router.get("/garmin/status", response_model=GarminStatus)
def garmin_status(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> GarminStatus:
    return GarminStatus(
        configured=is_garmin_configured(settings),
        night_count=health_repo.count_nights(db, DataSource.GARMIN),
        day_count=health_repo.count_days(db, DataSource.GARMIN),
        latest_day=health_repo.latest_day(db, DataSource.GARMIN),
        activity_count=activities_repo.count_activities(db, DataSource.GARMIN),
        activity_history_complete=sync_repo.is_cursor_completed(db, BACKFILL_CURSOR),
    )


@router.post("/import/health", response_model=ImportResult)
async def import_health_file(file: UploadFile, db: Session = Depends(get_db)) -> ImportResult:
    """Import a CSV (our template) or a Garmin export ``*_sleepData.json`` file."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File larger than 10 MB.")
    try:
        batch = parse_file(file.filename or "", content)
    except HealthProviderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    _, result = import_batch(db, batch)
    return ImportResult(
        nights=len(batch.sleep),
        days=len(batch.daily),
        created=result.created,
        updated=result.updated,
        warnings=result.warnings[:50],
    )
