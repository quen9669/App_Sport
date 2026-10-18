"""Tests for the health data routes (file upload, Garmin status and sync)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings

CSV = (
    b"date,sleep_duration_min,sleep_score,resting_hr,steps\n"
    b"2026-10-16,450,80,50,9000\n"
    b"2026-10-17,420,75,51,8000\n"
)


def upload(client: TestClient, name: str, content: bytes) -> Any:
    return client.post("/api/import/health", files={"file": (name, content, "text/csv")})


def test_csv_upload_imports_and_reimport_updates(client: TestClient) -> None:
    first = upload(client, "health.csv", CSV).json()
    second = upload(client, "health.csv", CSV).json()

    assert first["nights"] == 2 and first["created"] == 4  # 2 nights + 2 days
    assert second["created"] == 0 and second["updated"] == 4  # same file: no duplicates
    logs = client.get("/api/sync/logs", params={"source": "file_import"}).json()
    assert len(logs) == 2


def test_invalid_file_gives_clear_error(client: TestClient) -> None:
    response = upload(client, "health.txt", b"hello")

    assert response.status_code == 422
    assert ".csv" in response.json()["detail"]


def test_garmin_status_and_sync_require_configuration(client: TestClient) -> None:
    assert client.get("/api/garmin/status").json()["configured"] is False
    assert client.post("/api/sync/garmin").status_code == 400


def test_garmin_sync_route_starts_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "me@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    get_settings.cache_clear()
    # Replace the real background job: this test only checks the route itself.
    started: list[bool] = []
    monkeypatch.setattr("app.api.sync.run_garmin_sync", lambda *_a, **_k: started.append(True))

    response = client.post("/api/sync/garmin")

    assert response.status_code == 202
    assert started == [True]
