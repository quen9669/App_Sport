"""Tests for the Strava OAuth helper and the credential service (token refresh)."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from sqlalchemy.orm import Session

from app.db.models import SourceCredential
from app.integrations.strava.oauth import (
    TOKEN_URL,
    StravaOAuth,
    StravaOAuthError,
    TokenSet,
    has_required_scopes,
)
from app.services.crypto import TokenCipher, generate_key
from app.services.strava_auth import StravaCredentialService, StravaNotConnectedError
from tests.fixtures.strava import token_response


def make_oauth(http: httpx.Client) -> StravaOAuth:
    return StravaOAuth("12345", "secret", "http://localhost:8000/api/strava/callback", http)


def test_authorize_url_asks_for_required_scopes() -> None:
    with httpx.Client() as http:
        url = make_oauth(http).authorize_url(state="xyz")

    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["12345"]
    assert query["scope"] == ["read,activity:read_all"]
    assert query["state"] == ["xyz"]
    assert query["response_type"] == ["code"]


@pytest.mark.parametrize(
    ("granted", "ok"),
    [("read,activity:read_all", True), ("read,activity:read", False), (None, False)],
)
def test_has_required_scopes(granted: str | None, ok: bool) -> None:
    assert has_required_scopes(granted) is ok


@respx.mock
def test_exchange_code_posts_credentials() -> None:
    route = respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))

    with httpx.Client() as http:
        tokens = make_oauth(http).exchange_code("the-code")

    assert tokens.access_token == "access-1"
    assert tokens.athlete is not None and tokens.athlete.id == 987654
    body = parse_qs(route.calls.last.request.content.decode())
    assert body["grant_type"] == ["authorization_code"]
    assert body["code"] == ["the-code"]


@respx.mock
def test_token_error_does_not_leak_body() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"secret": "leak"}))

    with httpx.Client() as http, pytest.raises(StravaOAuthError) as error:
        make_oauth(http).exchange_code("bad")

    assert "leak" not in str(error.value)


def test_token_set_repr_hides_tokens() -> None:
    tokens = TokenSet(access_token="a-secret", refresh_token="r-secret", expires_at=0)

    assert "secret" not in repr(tokens)
    assert "secret" not in str(tokens)


# --- Credential service -----------------------------------------------------

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def make_service(db: Session, http: httpx.Client, cipher: TokenCipher) -> StravaCredentialService:
    return StravaCredentialService(db, cipher, make_oauth(http), now=lambda: NOW)


def store(service: StravaCredentialService, expires_at: datetime) -> None:
    service.save_tokens(
        TokenSet(
            access_token="old-access",
            refresh_token="old-refresh",
            expires_at=int(expires_at.timestamp()),
        ),
        scope="read,activity:read_all",
    )


def test_tokens_are_stored_encrypted(db: Session) -> None:
    cipher = TokenCipher(generate_key())
    with httpx.Client() as http:
        store(make_service(db, http, cipher), NOW + timedelta(hours=5))

    row = db.query(SourceCredential).one()
    assert "old-access" not in row.access_token_encrypted
    assert cipher.decrypt(row.access_token_encrypted) == "old-access"


@respx.mock
def test_valid_token_is_used_without_refresh(db: Session) -> None:
    route = respx.post(TOKEN_URL)
    with httpx.Client() as http:
        service = make_service(db, http, TokenCipher(generate_key()))
        store(service, NOW + timedelta(hours=5))

        assert service.get_access_token() == "old-access"

    assert route.call_count == 0


@respx.mock
def test_expiring_token_is_refreshed_and_new_refresh_token_saved(db: Session) -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=token_response("new-access", "new-refresh"))
    )
    cipher = TokenCipher(generate_key())
    with httpx.Client() as http:
        service = make_service(db, http, cipher)
        store(service, NOW + timedelta(minutes=2))  # inside the 5-minute margin

        assert service.get_access_token() == "new-access"

    body = parse_qs(route.calls.last.request.content.decode())
    assert body["refresh_token"] == ["old-refresh"]
    row = db.query(SourceCredential).one()
    assert cipher.decrypt(row.refresh_token_encrypted or "") == "new-refresh"


def test_not_connected_raises(db: Session) -> None:
    with httpx.Client() as http, pytest.raises(StravaNotConnectedError):
        make_service(db, http, TokenCipher(generate_key())).get_access_token()
