"""Tests for the scheduled synchronisations."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.scheduler import build_scheduler
from app.services import jobs


def test_scheduler_has_one_coalesced_interval_job(session_factory: sessionmaker[Session]) -> None:
    scheduler = build_scheduler(get_settings(), session_factory)

    job = scheduler.get_job("scheduled_syncs")

    assert job is not None
    assert job.trigger.interval.total_seconds() == 3 * 3600
    assert job.coalesce is True


def test_scheduled_run_skips_unconfigured_sources(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[str] = []
    monkeypatch.setattr(jobs, "run_strava_sync", lambda *_a: ran.append("strava"))
    monkeypatch.setattr(jobs, "run_garmin_sync", lambda *_a: ran.append("garmin"))

    jobs.run_scheduled_syncs(session_factory)

    assert ran == []


def test_one_failing_source_does_not_stop_the_others(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "me@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    get_settings.cache_clear()
    ran: list[str] = []

    def failing_garmin(*_args: object) -> None:
        ran.append("garmin")
        raise RuntimeError("boom")

    monkeypatch.setattr(jobs, "run_garmin_sync", failing_garmin)

    jobs.run_scheduled_syncs(session_factory)  # must not raise

    assert ran == ["garmin"]
