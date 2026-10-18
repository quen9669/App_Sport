"""Shared pytest fixtures. pytest loads this file automatically before the tests.

Every test gets:
- safe settings (a throwaway encryption key, fake Strava credentials);
- an empty in-memory SQLite database, wired into the app.
No test ever touches the real database or calls the real Strava API.
"""

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (registers the tables)
from app.config import get_settings
from app.db.base import Base
from app.db.session import provide_session_factory
from app.main import create_app

TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Environment variables for tests; settings are re-read for each test."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("GARMIN_EMAIL", "")
    monkeypatch.setenv("GARMIN_PASSWORD", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # tests never call the real model
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    monkeypatch.setenv("STRAVA_CLIENT_ID", "12345")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://frontend.test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def engine() -> Iterator[Engine]:
    # StaticPool + ":memory:" = one shared in-memory database for the whole test,
    # even across threads (FastAPI runs sync routes in a thread pool).
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """An HTTP client talking to a fresh app that uses the test database."""
    application = create_app()
    application.dependency_overrides[provide_session_factory] = lambda: session_factory
    with TestClient(application) as test_client:
        yield test_client
