"""Entry point of the backend: builds the FastAPI application.

Run it in development with ``make dev-backend`` (or
``uv run uvicorn app.main:app --reload``), then open http://localhost:8000/docs
to see and try every route.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    activities,
    auth,
    coach,
    dashboards,
    goals,
    health,
    health_data,
    maps,
    places,
    profile,
    race,
    smoking,
    strava,
    strength,
    sync,
)
from app.config import Settings, get_settings
from app.db.session import get_session_factory
from app.dependencies import require_auth
from app.frontend import mount_frontend
from app.logging_config import configure_logging
from app.scheduler import build_scheduler
from app.security import SecurityHeadersMiddleware
from app.services.auth import LoginThrottle

# Routers that need a signed-in user (all of them except health, auth and Strava,
# whose callback must stay reachable: Strava's redirect carries no cookie).
PROTECTED_ROUTERS: list[APIRouter] = [
    sync.router,
    health_data.router,
    profile.router,
    goals.router,
    dashboards.router,
    activities.router,
    strength.router,
    maps.router,
    places.router,
    smoking.router,
    race.router,
    coach.router,
]


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


def check_production(settings: Settings) -> None:
    """Refuse to start an exposed app without its protections."""
    if not settings.is_production:
        return
    if not settings.auth_enabled:
        raise RuntimeError("APP_ENV=production needs a password: run `make set-password`.")
    if not settings.token_encryption_key:
        raise RuntimeError("APP_ENV=production needs TOKEN_ENCRYPTION_KEY (run `make install`).")


def create_app() -> FastAPI:
    """Build and configure the application.

    Using a factory function (instead of a global built at import time) lets
    tests create a fresh app with their own settings.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    check_production(settings)

    # The interactive API docs (/docs) load scripts from a CDN: development only.
    docs = None if settings.is_production else "/docs"
    app = FastAPI(
        title="App Sport API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs,
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.login_throttle = LoginThrottle()

    # CORS: in development the browser blocks calls from the frontend (port 5173)
    # to the API (port 8000) unless the API explicitly allows that origin.
    # Credentials = the session cookie may travel with those calls.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware, https=settings.is_production)

    # Every route lives under /api so the frontend and the API never clash.
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(strava.router, prefix="/api")
    for router in PROTECTED_ROUTERS:
        app.include_router(router, prefix="/api", dependencies=[Depends(require_auth)])
    # Last: the interface catches every address the API did not answer.
    if settings.frontend_dist:
        mount_frontend(app, Path(settings.frontend_dist))
    return app


app = create_app()
