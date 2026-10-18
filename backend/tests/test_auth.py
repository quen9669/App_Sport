"""Sign-in (phase 6): password, session cookie, lockout after wrong passwords."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.session import provide_session_factory
from app.dependencies import get_now
from app.main import create_app
from app.services.auth import SESSION_COOKIE, LoginThrottle, hash_password, verify_password

PASSWORD = "correct horse battery staple"
# Hashing is slow on purpose: compute the fingerprint once for the whole file.
PASSWORD_HASH = hash_password(PASSWORD)
START = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class Clock:
    """A clock the tests move forward by hand."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_client(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session], clock: Clock
) -> Iterator[Callable[..., TestClient]]:
    """Build an app with or without a password (settings are read at creation)."""
    clients: list[TestClient] = []

    def build(password_hash: str = PASSWORD_HASH, env: str = "test") -> TestClient:
        monkeypatch.setenv("APP_PASSWORD_HASH", password_hash)
        monkeypatch.setenv("APP_ENV", env)
        get_settings.cache_clear()
        application = create_app()
        application.dependency_overrides[provide_session_factory] = lambda: session_factory
        application.dependency_overrides[get_now] = clock
        test_client = TestClient(application, base_url="https://testserver")
        test_client.__enter__()
        clients.append(test_client)
        return test_client

    yield build
    for test_client in clients:
        test_client.__exit__(None, None, None)


def login(client: TestClient, password: str = PASSWORD) -> int:
    return client.post("/api/auth/login", json={"password": password}).status_code


def test_without_password_everything_stays_open(make_client: Callable[..., TestClient]) -> None:
    client = make_client(password_hash="")
    assert client.get("/api/auth/status").json() == {"enabled": False, "authenticated": True}
    assert client.get("/api/goals").status_code == 200


def test_protected_routes_need_a_session(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    assert client.get("/api/auth/status").json() == {"enabled": True, "authenticated": False}
    assert client.get("/api/goals").status_code == 401
    assert client.get("/api/strava/status").status_code == 401
    # Still open: the "backend OK" check and Strava's return (protected by its own state).
    assert client.get("/api/health").status_code == 200
    callback = client.get("/api/strava/callback?state=unknown", follow_redirects=False)
    assert callback.status_code == 303


def test_login_sets_a_safe_cookie_then_logout_ends_the_session(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client()
    response = client.post("/api/auth/login", json={"password": PASSWORD})

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert f"max-age={30 * 24 * 3600}" in cookie
    assert client.get("/api/goals").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/goals").status_code == 401


def test_the_cookie_is_secure_in_production(make_client: Callable[..., TestClient]) -> None:
    client = make_client(env="production")
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    assert "secure" in response.headers["set-cookie"].lower()


def test_only_the_fingerprint_of_the_token_is_stored(
    make_client: Callable[..., TestClient], db: Session
) -> None:
    client = make_client()
    login(client)
    token = client.cookies[SESSION_COOKIE]
    stored = db.execute(text("SELECT token_hash FROM auth_session"))
    hashes = [row[0] for row in stored]
    assert len(hashes) == 1
    assert token not in hashes[0]


def test_a_session_expires_after_30_days(
    make_client: Callable[..., TestClient], clock: Clock
) -> None:
    client = make_client()
    login(client)
    clock.now = START + timedelta(days=29)
    assert client.get("/api/goals").status_code == 200
    clock.now = START + timedelta(days=30, seconds=1)
    assert client.get("/api/goals").status_code == 401


def test_five_wrong_passwords_lock_sign_in_for_15_minutes(
    make_client: Callable[..., TestClient], clock: Clock
) -> None:
    client = make_client()
    for _ in range(5):
        assert login(client, "wrong") == 401

    # Locked: even the right password is refused, with how long to wait.
    locked = client.post("/api/auth/login", json={"password": PASSWORD})
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 14 * 60
    assert "Trop d’essais" in locked.json()["detail"]

    clock.now = START + timedelta(minutes=15, seconds=1)
    assert login(client) == 200


def test_failures_far_apart_do_not_lock() -> None:
    throttle = LoginThrottle()
    for minute in range(0, 100, 20):  # 5 failures, one every 20 minutes
        throttle.record_failure(START + timedelta(minutes=minute))
    assert throttle.retry_after(START + timedelta(minutes=81)) == 0


def test_a_broken_fingerprint_never_lets_anyone_in() -> None:
    assert verify_password("not-an-argon2-hash", PASSWORD) is False
    assert verify_password(PASSWORD_HASH, "") is False


def test_production_refuses_to_start_without_a_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="make set-password"):
        create_app()


def test_failed_sign_in_logs_never_contain_the_password(
    make_client: Callable[..., TestClient], capsys: pytest.CaptureFixture[str]
) -> None:
    client = make_client()
    login(client, "my-secret-guess")
    # The app's own log handler writes to the terminal (see logging_config.py).
    logs = capsys.readouterr().err
    assert "Failed sign-in attempt" in logs
    assert "my-secret-guess" not in logs
