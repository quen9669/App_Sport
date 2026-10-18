"""Scheduled synchronisations with APScheduler.

APScheduler runs jobs in a background thread of the backend process: no extra
service to install. The scheduler starts with the app and stops with it (see
``lifespan`` in ``app/main.py``).
"""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.services.jobs import run_scheduled_syncs

logger = logging.getLogger(__name__)


def build_scheduler(
    settings: Settings, session_factory: sessionmaker[Session]
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        run_scheduled_syncs,
        trigger="interval",
        hours=settings.sync_interval_hours,
        args=[session_factory],
        id="scheduled_syncs",
        # First run one minute after startup, not immediately: lets the app settle.
        next_run_time=datetime.now(UTC) + timedelta(minutes=1),
        # If the PC was asleep and several runs were missed, run once, not N times.
        coalesce=True,
        max_instances=1,
    )
    logger.info("Scheduled syncs every %s h", settings.sync_interval_hours)
    return scheduler
