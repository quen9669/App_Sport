"""Entry point of the backend: builds the FastAPI application.

Run it in development with ``make dev-backend`` (or
``uv run uvicorn app.main:app --reload``), then open http://localhost:8000/docs
to see and try every route.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    activities,
    dashboards,
    goals,
    health,
    health_data,
    profile,
    strava,
    strength,
    sync,
)
from app.config import get_settings
from app.db.session import get_session_factory
from app.logging_config import configure_logging
from app.scheduler import build_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Code run when the server starts (before ``yield``) and stops (after)."""
    settings = get_settings()
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler(settings, get_session_factory())
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """Build and configure the application.

    Using a factory function (instead of a global built at import time) lets
    tests create a fresh app with their own settings.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="App Sport API", version="0.1.0", lifespan=lifespan)

    # CORS: the browser blocks calls from the frontend (port 5173) to the API
    # (port 8000) unless the API explicitly allows that origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Every route lives under /api so the frontend and the API never clash.
    app.include_router(health.router, prefix="/api")
    app.include_router(strava.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")
    app.include_router(health_data.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    app.include_router(goals.router, prefix="/api")
    app.include_router(dashboards.router, prefix="/api")
    app.include_router(activities.router, prefix="/api")
    app.include_router(strength.router, prefix="/api")
    return app


app = create_app()
