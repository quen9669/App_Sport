"""Sync jobs that run outside an HTTP request: background tasks and the scheduler.

Each job opens its own database session (the request that triggered it is
already finished) and builds the clients it needs from the settings.
"""

import logging

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import SyncLog
from app.db.models.enums import DataSource, SyncKind
from app.dependencies import HTTP_TIMEOUT_S, build_strava_oauth
from app.integrations.health.garmin_connect import GarminConnectProvider, login_with_library
from app.integrations.strava.client import StravaClient
from app.repositories import credentials as credentials_repo
from app.services.crypto import TokenCipher
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


def build_garmin_provider(settings: Settings) -> GarminConnectProvider:
    return GarminConnectProvider(
        login=lambda: login_with_library(
            settings.garmin_email, settings.garmin_password, settings.garmin_tokenstore
        )
    )


def run_garmin_sync(
    session_factory: sessionmaker[Session], kind: SyncKind = SyncKind.MANUAL
) -> SyncLog:
    settings = get_settings()
    with session_factory() as db:
        return run_provider_sync(
            db, build_garmin_provider(settings), kind, settings.garmin_initial_days
        )


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
