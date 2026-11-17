"""Monitoring settings page: sync, memory and coach checks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models.coach import CoachCall
from app.db.models.sync import SyncLog
from app.services.monitoring import (
    coach_health,
    memory_health,
    overall,
    source_health,
)

NOW = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)


def add_run(
    db: Session, source: str, status: str, hours_ago: float, error: str | None = None
) -> None:
    started = NOW - timedelta(hours=hours_ago)
    db.add(
        SyncLog(
            source=source,
            kind="scheduled",
            status=status,
            started_at=started,
            finished_at=started + timedelta(minutes=2),
            error=error,
        )
    )
    db.commit()


def test_a_source_never_synced_is_unknown_not_broken(db: Session) -> None:
    health = source_health(db, "strava", NOW)
    assert health.status == "unknown"
    assert health.last_success_at is None


def test_a_recent_success_is_ok(db: Session) -> None:
    add_run(db, "garmin", "success", hours_ago=2)
    health = source_health(db, "garmin", NOW)
    assert health.status == "ok"
    assert health.last_success_at == NOW - timedelta(hours=2)


def test_partial_runs_count_as_success(db: Session) -> None:
    add_run(db, "strava", "partial", hours_ago=1)
    assert source_health(db, "strava", NOW).status == "ok"


def test_a_failed_last_run_is_a_warning_and_is_counted(db: Session) -> None:
    add_run(db, "garmin", "success", hours_ago=4)
    add_run(db, "garmin", "failed", hours_ago=1, error="Garmin login refused")
    health = source_health(db, "garmin", NOW)
    assert health.status == "warning"
    assert health.failures_7d == 1
    assert health.last_error == "Garmin login refused"


@pytest.mark.parametrize(("hours", "expected"), [(5, "ok"), (8, "warning"), (13, "error")])
def test_status_follows_the_age_of_the_last_success(
    db: Session, hours: float, expected: str
) -> None:
    add_run(db, "garmin", "success", hours_ago=hours)
    assert source_health(db, "garmin", NOW).status == expected


def test_old_failures_are_not_counted(db: Session) -> None:
    add_run(db, "strava", "failed", hours_ago=24 * 8)
    add_run(db, "strava", "success", hours_ago=1)
    assert source_health(db, "strava", NOW).failures_7d == 0


def test_memory_against_the_docker_limit(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("214000000\n")
    (tmp_path / "memory.max").write_text("536870912\n")
    health = memory_health(tmp_path)
    assert (health.status, health.used_bytes, health.limit_bytes) == ("ok", 214000000, 536870912)

    (tmp_path / "memory.current").write_text("500000000\n")
    assert memory_health(tmp_path).status == "warning"


def test_memory_without_limit_or_outside_docker(tmp_path: Path) -> None:
    assert memory_health(tmp_path).status == "unknown"
    (tmp_path / "memory.current").write_text("1000\n")
    (tmp_path / "memory.max").write_text("max\n")
    health = memory_health(tmp_path)
    assert (health.status, health.limit_bytes) == ("ok", None)


def test_coach_status(db: Session, settings: Settings) -> None:
    assert coach_health(db, NOW, settings).status == "unknown"  # no key in tests
    enabled = settings.model_copy(update={"omniroute_api_key": "k"})
    assert coach_health(db, NOW, enabled).status == "ok"
    db.add(
        CoachCall(
            created_at=NOW - timedelta(days=1),
            coach="training",
            model="m",
            input_tokens=0,
            output_tokens=0,
            cost_eur=50.0,
            latency_ms=1,
            error="LLMError",
        )
    )
    db.commit()
    # The last call failed (e.g. OmniRoute refused it): "◆ Dégradé", never a limit.
    health = coach_health(db, NOW, enabled)
    assert (health.status, health.enabled, health.spent_eur) == ("warning", True, 50.0)


def test_the_worst_status_wins() -> None:
    assert overall(["ok", "unknown"]) == "ok"
    assert overall(["ok", "warning", "unknown"]) == "warning"
    assert overall(["warning", "error"]) == "error"


def test_route_answers_without_any_health_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    monkeypatch.setenv("GRAFANA_URL", "http://grafana.test/d/app-sport")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.get("/api/monitoring")
    assert response.status_code == 200
    body = response.json()
    assert [s["source"] for s in body["sources"]] == ["garmin", "strava"]
    assert body["status"] == "ok"  # nothing synced yet: unknown, not an alarm
    assert body["grafana_url"] == "http://grafana.test/d/app-sport"
    assert set(body) == {
        "status",
        "checked_at",
        "started_at",
        "sources",
        "memory",
        "coach",
        "database_bytes",
        "activities_7d",
        "grafana_url",
    }
