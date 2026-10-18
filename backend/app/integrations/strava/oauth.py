"""Strava OAuth2: build the consent URL, exchange the code for tokens, refresh them.

The flow ("authorization code" grant):
1. We send the browser to Strava's consent page (:meth:`StravaOAuth.authorize_url`).
2. The user accepts; Strava redirects back to our callback with a one-time ``code``.
3. The backend exchanges that code for an access token (valid 6 hours) and a
   refresh token (:meth:`StravaOAuth.exchange_code`).
4. Before the access token expires, we trade the refresh token for a new pair
   (:meth:`StravaOAuth.refresh`).
"""

import contextlib
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"

# "read": public profile; "activity:read_all": all activities, including private ones.
REQUIRED_SCOPES = ("read", "activity:read_all")


class StravaOAuthError(RuntimeError):
    """Strava refused a token request (bad code, revoked access...)."""


class StravaAthlete(BaseModel):
    id: int


class TokenSet(BaseModel):
    """Tokens returned by Strava's token endpoint (only the fields we use)."""

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp (seconds)
    athlete: StravaAthlete | None = None  # only present on the first exchange

    @property
    def expires_at_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.expires_at, tz=UTC)

    def __repr__(self) -> str:
        # Never print tokens, even while debugging.
        return f"TokenSet(expires_at={self.expires_at}, access_token=***, refresh_token=***)"

    __str__ = __repr__


def has_required_scopes(granted: str | None) -> bool:
    """True if the comma-separated ``granted`` scopes include everything we need."""
    granted_set = {scope.strip() for scope in (granted or "").split(",")}
    return all(scope in granted_set for scope in REQUIRED_SCOPES)


class StravaOAuth:
    def __init__(
        self, client_id: str, client_secret: str, redirect_uri: str, http: httpx.Client
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http

    @property
    def is_configured(self) -> bool:
        """False until STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET are set in .env."""
        return bool(self._client_id and self._client_secret)

    def authorize_url(self, state: str) -> str:
        """URL of Strava's consent page. ``state`` protects against forged callbacks."""
        query = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",  # don't ask again if already accepted
            "scope": ",".join(REQUIRED_SCOPES),
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def exchange_code(self, code: str) -> TokenSet:
        return self._token_request({"grant_type": "authorization_code", "code": code})

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def deauthorize(self, access_token: str) -> None:
        """Revoke our access on Strava's side (best effort: errors are ignored)."""
        # contextlib.suppress = "run this, and silently ignore this kind of error".
        with contextlib.suppress(httpx.HTTPError):
            self._http.post(DEAUTHORIZE_URL, data={"access_token": access_token})

    def _token_request(self, extra: dict[str, str]) -> TokenSet:
        data = {"client_id": self._client_id, "client_secret": self._client_secret, **extra}
        response = self._http.post(TOKEN_URL, data=data)
        if response.status_code != 200:
            # Only the status code: the body could contain sensitive details.
            raise StravaOAuthError(f"Strava token request failed (HTTP {response.status_code})")
        return TokenSet.model_validate(response.json())
