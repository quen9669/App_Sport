"""Synchronisation routes: start a sync by hand, read the sync journal."""

import contextlib
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models.enums import DataSource, SyncKind
from app.db.session import get_db, provide_session_factory
from app.repositories import credentials as credentials_repo
from app.repositories import sync as sync_repo
from app.services.health_sync import HealthSyncAlreadyRunningError, is_garmin_sync_running
from app.services.jobs import is_garmin_configured, run_garmin_sync, run_strava_sync
from app.services.strava_sync import SyncAlreadyRunningError, is_sync_running

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncStarted(BaseModel):
    status: str


class SyncLogOut(BaseModel):
    # from_attributes: build this model directly from a SyncLog database object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    items_created: int
    items_updated: int
    error: str | None


def _strava_in_background(factory: sessionmaker[Session]) -> None:
    # The button may be clicked while a scheduled run is going: nothing to do then.
    with contextlib.suppress(SyncAlreadyRunningError):
        run_strava_sync(factory, SyncKind.MANUAL)


def _garmin_in_background(factory: sessionmaker[Session]) -> None:
    with contextlib.suppress(HealthSyncAlreadyRunningError):
        run_garmin_sync(factory, SyncKind.MANUAL)


@router.post("/strava", response_model=SyncStarted, status_code=status.HTTP_202_ACCEPTED)
def start_strava_sync(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    factory: sessionmaker[Session] = Depends(provide_session_factory),
) -> SyncStarted:
    """Start a Strava sync and answer immediately (202 = accepted, work in progress).

    A sync can take minutes (quotas), far too long to keep the browser waiting:
    it runs after the response is sent. Follow it with ``GET /api/sync/logs``.
    """
    if credentials_repo.get_credential(db, DataSource.STRAVA) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Strava is not connected.")
    if is_sync_running():
        raise HTTPException(status.HTTP_409_CONFLICT, "A Strava sync is already running.")
    background.add_task(_strava_in_background, factory)
    return SyncStarted(status="started")


@router.post("/garmin", response_model=SyncStarted, status_code=status.HTTP_202_ACCEPTED)
def start_garmin_sync(
    background: BackgroundTasks,
    factory: sessionmaker[Session] = Depends(provide_session_factory),
    settings: Settings = Depends(get_settings),
) -> SyncStarted:
    """Start a Garmin sync in the background (same pattern as Strava)."""
    if not is_garmin_configured(settings):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Garmin is not configured: set GARMIN_EMAIL and GARMIN_PASSWORD in .env.",
        )
    if is_garmin_sync_running():
        raise HTTPException(status.HTTP_409_CONFLICT, "A Garmin sync is already running.")
    background.add_task(_garmin_in_background, factory)
    return SyncStarted(status="started")


@router.get("/logs", response_model=list[SyncLogOut])
def get_logs(
    source: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SyncLogOut]:
    return [SyncLogOut.model_validate(log) for log in sync_repo.list_logs(db, limit, source)]
