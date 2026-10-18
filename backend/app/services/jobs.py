"""Sync jobs that run outside an HTTP request: background tasks and the scheduler.

Each job opens its own database session (the request that triggered it is
already finished) and builds the clients it needs from the settings.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import SyncLog
from app.db.models.enums import DataSource, SyncKind
from app.db.types import utc_now
from app.dependencies import HTTP_TIMEOUT_S, build_strava_oauth
from app.integrations.health.garmin_connect import (
    GarminApi,
    GarminConnectProvider,
    login_with_library,
)
from app.integrations.strava.client import StravaClient
from app.repositories import credentials as credentials_repo
from app.services.backup import backup_database
from app.services.crypto import TokenCipher
from app.services.garmin_activity_sync import GarminActivitySyncService
from app.services.health_sync import run_provider_sync
from app.services.strava_auth import StravaCredentialService
from app.services.strava_sync import StravaSyncService, SyncLimits

logger = logging.getLogger(__name__)


def run_strava_sync(
    session_factory: sessionmaker[Session],
    kind: SyncKind = SyncKind.MANUAL,
    limits: SyncLimits | None = None,
) -> SyncLog:
    settings = get_settings()
    with session_factory() as db, httpx.Client(timeout=HTTP_TIMEOUT_S) as http:
        credentials = StravaCredentialService(
            db, TokenCipher(settings.token_encryption_key), build_strava_oauth(settings, http)
        )
        client = StravaClient(http, access_token=credentials.get_access_token)
        return StravaSyncService(db, client, limits).run(kind)


def is_garmin_configured(settings: Settings) -> bool:
    return bool(settings.garmin_email and settings.garmin_password)


def garmin_login_once(settings: Settings) -> Callable[[], GarminApi]:
    """A function that logs in to Garmin on its first call and then reuses the client.

    Health data and activities share it, so one Garmin sync logs in only once.
    """
    client: list[GarminApi] = []  # a list so the inner function can fill it

    def login() -> GarminApi:
        if not client:
            client.append(
                login_with_library(
                    settings.garmin_email, settings.garmin_password, settings.garmin_tokenstore
                )
            )
        return client[0]

    return login


def run_garmin_sync(
    session_factory: sessionmaker[Session],
    kind: SyncKind = SyncKind.MANUAL,
    login: Callable[[], GarminApi] | None = None,
) -> SyncLog:
    """Health data first (sleep, HRV...), then activities. Returns the activities' log.

    Each part has its own sync_log entry, so a failure in one is visible and
    does not hide the result of the other.
    """
    settings = get_settings()
    login = login or garmin_login_once(settings)
    with session_factory() as db:
        run_provider_sync(
            db, GarminConnectProvider(login=login), kind, settings.garmin_initial_days
        )
        return GarminActivitySyncService(db, login).run(kind)


def run_scheduled_syncs(session_factory: sessionmaker[Session]) -> None:
    """What the scheduler runs every few hours: each configured source in turn.

    A failure in one source is recorded in its sync_log and never prevents the
    next source from running.
    """
    settings = get_settings()
    with session_factory() as db:
        strava_connected = credentials_repo.get_credential(db, DataSource.STRAVA) is not None
    if strava_connected:
        try:
            run_strava_sync(session_factory, SyncKind.SCHEDULED)
        except Exception:  # e.g. a manual sync already running
            logger.exception("Scheduled Strava sync could not run")
    if is_garmin_configured(settings):
        try:
            run_garmin_sync(session_factory, SyncKind.SCHEDULED)
        except Exception:
            logger.exception("Scheduled Garmin sync could not run")


def run_nightly_backup() -> None:
    """Scheduled every night: a copy of the database, the last BACKUP_KEEP kept."""
    settings = get_settings()
    try:
        backup_database(
            settings.database_url, Path(settings.backup_dir), settings.backup_keep, utc_now()
        )
    except Exception:
        # A failed backup must never stop the app; the log says what happened.
        logger.exception("Nightly backup failed")
