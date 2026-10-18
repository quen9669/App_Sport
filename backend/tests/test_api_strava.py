"""Tests for the Strava connection routes and the sync routes."""

from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.strava import oauth_states
from app.db.models import Activity, SourceCredential
from app.integrations.strava.oauth import TOKEN_URL
from tests.fixtures.strava import FakeStravaApi, make_history, token_response


@pytest.fixture
def mock_router() -> Iterator[respx.MockRouter]:
    # Let calls to the local test app through; only Strava URLs are mocked.
    with respx.mock(assert_all_called=False) as router:
        yield router


def connect(client: TestClient) -> None:
    """Go through the OAuth callback as if the user had accepted on Strava."""
    state = oauth_states.create()
    response = client.get(
        "/api/strava/callback",
        params={"state": state, "code": "abc", "scope": "read,activity:read_all"},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("strava=connected")


def test_status_when_not_connected(client: TestClient) -> None:
    body = client.get("/api/strava/status").json()

    assert body == {
        "configured": True,
        "connected": False,
        "athlete_id": None,
        "scope": None,
        "activity_count": 0,
        "history_complete": False,
    }


def test_connect_redirects_to_strava_with_state(client: TestClient) -> None:
    response = client.get("/api/strava/connect", follow_redirects=False)

    assert response.status_code == 307
    location = urlparse(response.headers["location"])
    assert location.netloc == "www.strava.com"
    state = parse_qs(location.query)["state"][0]
    assert oauth_states.consume(state)


def test_connect_without_strava_keys_explains_what_to_do(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("STRAVA_CLIENT_ID", "")
    get_settings.cache_clear()

    response = client.get("/api/strava/connect", follow_redirects=False)

    assert response.status_code == 503
    assert "STRAVA_CLIENT_ID" in response.json()["detail"]


def test_callback_with_unknown_state_is_rejected(client: TestClient, db: Session) -> None:
    response = client.get(
        "/api/strava/callback",
        params={"state": "forged", "code": "abc", "scope": "read,activity:read_all"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "http://frontend.test/sources?strava=invalid_state"
    assert db.query(SourceCredential).count() == 0


def test_callback_without_private_activities_scope(client: TestClient, db: Session) -> None:
    response = client.get(
        "/api/strava/callback",
        params={"state": oauth_states.create(), "code": "abc", "scope": "read"},
        follow_redirects=False,
    )

    assert response.headers["location"].endswith("strava=missing_scope")
    assert db.query(SourceCredential).count() == 0


def test_callback_stores_encrypted_tokens(
    client: TestClient, db: Session, mock_router: respx.MockRouter
) -> None:
    mock_router.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))

    connect(client)

    credential = db.query(SourceCredential).one()
    assert credential.external_account_id == "987654"
    assert "access-1" not in credential.access_token_encrypted
    assert client.get("/api/strava/status").json()["connected"] is True


def test_disconnect_forgets_tokens(
    client: TestClient, db: Session, mock_router: respx.MockRouter
) -> None:
    mock_router.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))
    mock_router.post("https://www.strava.com/oauth/deauthorize").mock(
        return_value=httpx.Response(200)
    )
    connect(client)

    assert client.delete("/api/strava/connection").status_code == 204
    assert db.query(SourceCredential).count() == 0


def test_manual_sync_requires_connection(client: TestClient) -> None:
    assert client.post("/api/sync/strava").status_code == 400


def test_manual_sync_imports_activities_and_logs_run(
    client: TestClient, db: Session, mock_router: respx.MockRouter
) -> None:
    FakeStravaApi(make_history(12)).install(mock_router)
    connect(client)

    # TestClient runs background tasks right after the response.
    response = client.post("/api/sync/strava")

    assert response.status_code == 202
    assert db.query(Activity).count() == 12
    logs = client.get("/api/sync/logs").json()
    assert logs[0]["source"] == "strava"
    assert logs[0]["status"] == "success"
    assert logs[0]["items_created"] == 12
    assert client.get("/api/strava/status").json()["history_complete"] is True
