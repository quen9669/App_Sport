"""Profile and body measurements: validation bounds and one weight per day."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.profile import age_on


def test_age_counts_full_years() -> None:
    assert age_on(date(1990, 10, 19), date(2026, 10, 18)) == 35  # birthday tomorrow
    assert age_on(date(1990, 10, 18), date(2026, 10, 18)) == 36


def test_empty_profile_is_created_on_first_read(client: TestClient) -> None:
    body = client.get("/api/profile").json()
    assert body["height_cm"] is None
    assert body["age"] is None


def test_save_profile(client: TestClient) -> None:
    payload = {
        "height_cm": 180,
        "sex": "male",
        "birth_date": "1990-05-01",
        "max_heartrate": 188,
        "resting_heartrate": 52,
        "experience_level": "intermediate",
        "injuries": "Genou gauche fragile",
    }
    body = client.put("/api/profile", json=payload).json()
    assert body["height_cm"] == 180
    assert body["age"] == age_on(date(1990, 5, 1), date.today())
    assert client.get("/api/profile").json()["injuries"] == "Genou gauche fragile"

    # PUT replaces everything: a field left out is cleared.
    assert client.put("/api/profile", json={"height_cm": 181}).json()["sex"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"height_cm": 99},
        {"height_cm": 251},
        {"max_heartrate": 250},
        {"resting_heartrate": 20},
        {"sex": "robot"},
        {"experience_level": "god"},
        {"injuries": "x" * 2001},
        {"birth_date": (date.today() - timedelta(days=365 * 5)).isoformat()},
        {"birth_date": "1900-01-01"},
    ],
)
def test_profile_bounds(client: TestClient, payload: dict[str, object]) -> None:
    assert client.put("/api/profile", json=payload).status_code == 422


def test_body_metrics_one_per_day(client: TestClient) -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)
    client.post("/api/body-metrics", json={"measured_on": yesterday.isoformat(), "weight_kg": 80})
    client.post("/api/body-metrics", json={"measured_on": today.isoformat(), "weight_kg": 79.8})
    # Weighing again the same day replaces the value.
    client.post(
        "/api/body-metrics",
        json={"measured_on": today.isoformat(), "weight_kg": 79.6, "waist_cm": 85},
    )
    metrics = client.get("/api/body-metrics").json()
    assert [m["weight_kg"] for m in metrics] == [80, 79.6]
    assert metrics[1]["waist_cm"] == 85

    assert client.delete(f"/api/body-metrics/{metrics[0]['id']}").status_code == 204
    assert len(client.get("/api/body-metrics").json()) == 1
    assert client.delete(f"/api/body-metrics/{metrics[0]['id']}").status_code == 404


def test_body_metrics_days_filter(client: TestClient) -> None:
    old = (date.today() - timedelta(days=100)).isoformat()
    client.post("/api/body-metrics", json={"measured_on": old, "weight_kg": 82})
    client.post(
        "/api/body-metrics", json={"measured_on": date.today().isoformat(), "weight_kg": 80}
    )
    assert len(client.get("/api/body-metrics", params={"days": 30}).json()) == 1
    assert len(client.get("/api/body-metrics", params={"days": 365}).json()) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"weight_kg": 25},
        {"weight_kg": 301},
        {"weight_kg": 80, "body_fat_pct": 2},
        {"weight_kg": 80, "waist_cm": 250},
    ],
)
def test_body_metric_bounds(client: TestClient, payload: dict[str, object]) -> None:
    payload = {"measured_on": date.today().isoformat(), **payload}
    assert client.post("/api/body-metrics", json=payload).status_code == 422


def test_body_metric_not_in_future(client: TestClient) -> None:
    future = (date.today() + timedelta(days=5)).isoformat()
    response = client.post("/api/body-metrics", json={"measured_on": future, "weight_kg": 80})
    assert response.status_code == 422
