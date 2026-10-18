"""Sign-in routes (phase 6): status, login and logout.

These routes are reachable without being signed in (the others are not, see
``require_auth`` in ``app/dependencies.py``).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.dependencies import get_login_throttle, get_now
from app.services.auth import (
    SESSION_COOKIE,
    LoginThrottle,
    create_session,
    delete_session,
    session_is_valid,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    # False = no password set: the app opens without a login screen.
    enabled: bool
    authenticated: bool


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.get("/status", response_model=AuthStatus)
def get_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> AuthStatus:
    if not settings.auth_enabled:
        return AuthStatus(enabled=False, authenticated=True)
    valid = session_is_valid(db, request.cookies.get(SESSION_COOKIE), now)
    return AuthStatus(enabled=True, authenticated=valid)


@router.post("/login", response_model=AuthStatus)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    throttle: LoginThrottle = Depends(get_login_throttle),
) -> AuthStatus:
    if not settings.auth_enabled:
        return AuthStatus(enabled=False, authenticated=True)
    wait = throttle.retry_after(now)
    if wait:
        # 429 = too many requests; Retry-After tells the screen how long to wait.
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop d’essais. Réessaie dans {wait // 60 + 1} min.",
            headers={"Retry-After": str(wait)},
        )
    if not verify_password(settings.app_password_hash, body.password):
        throttle.record_failure(now)
        # Logged for the record, without the password (and without the address,
        # which is always the proxy's behind Tailscale).
        logger.warning("Failed sign-in attempt")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe incorrect.")
    throttle.record_success()
    token = create_session(db, now, settings.session_days, request.headers.get("user-agent"))
    set_session_cookie(response, token, settings)
    logger.info("Signed in")
    return AuthStatus(enabled=True, authenticated=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    delete_session(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    """The cookie that keeps the device signed in.

    - HttpOnly: page scripts cannot read it (an injected script could not steal it);
    - Secure (production): only sent over HTTPS;
    - SameSite=Strict: never sent by another site's links or forms (no CSRF).
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 3600,
        path="/",
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )
