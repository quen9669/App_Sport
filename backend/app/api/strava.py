"""Strava connection routes: status, connect (OAuth), callback, disconnect."""

import secrets
import threading
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models.enums import DataSource
from app.db.session import get_db
from app.dependencies import get_cipher, get_strava_oauth, require_auth
from app.integrations.strava.oauth import StravaOAuth, StravaOAuthError, has_required_scopes
from app.repositories import activities as activities_repo
from app.repositories import credentials as credentials_repo
from app.repositories import sync as sync_repo
from app.services.crypto import TokenCipher
from app.services.strava_auth import StravaCredentialService
from app.services.strava_sync import BACKFILL_CURSOR

router = APIRouter(prefix="/strava", tags=["strava"])


class OAuthStateStore:
    """Remembers the random ``state`` values we sent to Strava, for 10 minutes.

    When Strava redirects back, the callback must carry one of them. This
    proves the callback answers a connection *we* started (protection against
    "CSRF": a malicious site linking your account to someone else's).
    Kept in memory: fine for a single-user app running one process.
    """

    TTL_S = 600

    def __init__(self) -> None:
        self._states: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        state = secrets.token_urlsafe(24)
        with self._lock:
            now = time.monotonic()
            # Drop expired states so the dict never grows forever.
            self._states = {s: exp for s, exp in self._states.items() if exp > now}
            self._states[state] = now + self.TTL_S
        return state

    def consume(self, state: str) -> bool:
        """True if ``state`` is known and fresh. A state can be used only once."""
        with self._lock:
            expires = self._states.pop(state, None)
        return expires is not None and expires > time.monotonic()


oauth_states = OAuthStateStore()


class StravaStatus(BaseModel):
    configured: bool  # client id/secret present in .env
    connected: bool
    athlete_id: str | None
    scope: str | None
    activity_count: int
    history_complete: bool


@router.get("/status", response_model=StravaStatus, dependencies=[Depends(require_auth)])
def get_status(
    db: Session = Depends(get_db),
    oauth: StravaOAuth = Depends(get_strava_oauth),
) -> StravaStatus:
    credential = credentials_repo.get_credential(db, DataSource.STRAVA)
    return StravaStatus(
        configured=oauth.is_configured,
        connected=credential is not None,
        athlete_id=credential.external_account_id if credential else None,
        scope=credential.scope if credential else None,
        activity_count=activities_repo.count_activities(db, DataSource.STRAVA),
        history_complete=sync_repo.is_cursor_completed(db, BACKFILL_CURSOR),
    )


@router.get("/connect", dependencies=[Depends(require_auth)])
def connect(oauth: StravaOAuth = Depends(get_strava_oauth)) -> RedirectResponse:
    """Send the browser to Strava's consent page."""
    if not oauth.is_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Strava is not configured: set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env.",
        )
    return RedirectResponse(oauth.authorize_url(oauth_states.create()))


@router.get("/callback")
def callback(
    state: str = Query(""),
    code: str | None = Query(None),
    scope: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
    oauth: StravaOAuth = Depends(get_strava_oauth),
    cipher: TokenCipher = Depends(get_cipher),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Strava sends the browser back here. We always end on the frontend "Sources" page,
    with ``?strava=<result>`` telling it what happened."""

    def back_to_frontend(result: str) -> RedirectResponse:
        query = urlencode({"strava": result})
        return RedirectResponse(
            f"{settings.frontend_url}/sources?{query}", status.HTTP_303_SEE_OTHER
        )

    if not oauth_states.consume(state):
        return back_to_frontend("invalid_state")
    if error or not code:
        return back_to_frontend("denied")  # the user clicked "Cancel" on Strava
    if not has_required_scopes(scope):
        # The user unticked "View data about your private activities": we need it.
        return back_to_frontend("missing_scope")
    try:
        tokens = oauth.exchange_code(code)
    except StravaOAuthError:
        return back_to_frontend("error")
    StravaCredentialService(db, cipher, oauth).save_tokens(tokens, scope=scope)
    return back_to_frontend("connected")


@router.delete(
    "/connection", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)]
)
def disconnect(
    db: Session = Depends(get_db),
    oauth: StravaOAuth = Depends(get_strava_oauth),
    cipher: TokenCipher = Depends(get_cipher),
) -> None:
    """Forget the Strava tokens. Already imported activities are kept."""
    StravaCredentialService(db, cipher, oauth).disconnect()
