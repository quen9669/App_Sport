"""Shared FastAPI dependencies: objects that routes receive through ``Depends(...)``.

Declaring them here (instead of creating them inside each route) means tests can
replace any of them with ``app.dependency_overrides``.
"""

from collections.abc import Iterator

import httpx
from fastapi import Depends, HTTPException, status

from app.config import Settings, get_settings
from app.integrations.strava.oauth import StravaOAuth
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
