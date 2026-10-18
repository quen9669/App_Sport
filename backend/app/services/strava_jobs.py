"""Entry point to run a Strava sync outside of an HTTP request.

Used by the "Synchronise now" button (as a background task) and, in the next
step, by the scheduler. It builds everything the sync needs from scratch, with
its own database session, because the request that triggered it is already over.
"""

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import SyncLog
from app.db.models.enums import SyncKind
from app.dependencies import HTTP_TIMEOUT_S, build_strava_oauth
from app.integrations.strava.client import StravaClient
from app.services.crypto import TokenCipher
from app.services.strava_auth import StravaCredentialService
from app.services.strava_sync import StravaSyncService, SyncLimits


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
