"""Shared FastAPI dependencies: objects that routes receive through ``Depends(...)``.

Declaring them here (instead of creating them inside each route) means tests can
replace any of them with ``app.dependency_overrides``.
"""

from collections.abc import Iterator
from datetime import datetime

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.db.types import utc_now
from app.integrations.strava.oauth import StravaOAuth
from app.services.auth import SESSION_COOKIE, LoginThrottle, session_is_valid
from app.services.crypto import TokenCipher, TokenEncryptionError

HTTP_TIMEOUT_S = 30.0


def get_http_client() -> Iterator[httpx.Client]:
    """An HTTP client for one request, closed afterwards."""
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        yield client


def get_cipher(settings: Settings = Depends(get_settings)) -> TokenCipher:
    try:
        return TokenCipher(settings.token_encryption_key)
    except TokenEncryptionError as exc:
        # 503 = the server is not ready to do this; the message says how to fix it.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None


def build_strava_oauth(settings: Settings, http: httpx.Client) -> StravaOAuth:
    return StravaOAuth(
        client_id=settings.strava_client_id,
        client_secret=settings.strava_client_secret,
        redirect_uri=settings.strava_redirect_uri,
        http=http,
    )


def get_strava_oauth(
    settings: Settings = Depends(get_settings),
    http: httpx.Client = Depends(get_http_client),
) -> StravaOAuth:
    return build_strava_oauth(settings, http)


def get_now() -> datetime:
    """The current time; tests replace it to check session expiry and lockouts."""
    return utc_now()


def get_login_throttle(request: Request) -> LoginThrottle:
    """The app's single wrong-password counter (created in ``create_app``)."""
    throttle: LoginThrottle = request.app.state.login_throttle
    return throttle


def require_auth(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> None:
    """Guard of every protected route: answer 401 unless the session cookie is valid.

    Without a password (development on the PC), everything stays open.
    """
    if not settings.auth_enabled:
        return
    if not session_is_valid(db, request.cookies.get(SESSION_COOKIE), now):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connexion requise.")
