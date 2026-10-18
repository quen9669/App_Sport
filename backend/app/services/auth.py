"""Sign-in for the single user of the app (phase 6).

- The password is checked against its Argon2 fingerprint (``APP_PASSWORD_HASH``):
  Argon2 is deliberately slow, so guessing passwords from a stolen fingerprint
  takes ages.
- A successful sign-in creates a random session token. The browser keeps it in
  a cookie; the database only keeps its SHA-256 fingerprint (see ``AuthSession``).
- ``LoginThrottle`` blocks sign-in for 15 minutes after 5 wrong passwords, so
  nobody can try thousands of passwords.
"""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AuthSession

# Name of the cookie holding the session token.
SESSION_COOKIE = "app_sport_session"
# last_seen_at is refreshed at most this often, to avoid a write on every request.
LAST_SEEN_STEP = timedelta(hours=1)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """The Argon2 fingerprint to store in .env (salt and settings included)."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True if ``password`` matches; False for a wrong password or a broken fingerprint."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, now: datetime, days: int, user_agent: str | None) -> str:
    """Store a new session and return its token (to put in the cookie)."""
    token = secrets.token_urlsafe(32)  # 256 random bits: impossible to guess
    db.add(
        AuthSession(
            token_hash=token_fingerprint(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=days),
            user_agent=(user_agent or "")[:200] or None,
        )
    )
    # Expired sessions are useless: clean them up while we are here.
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    db.commit()
    return token


def session_is_valid(db: Session, token: str | None, now: datetime) -> bool:
    if not token:
        return False
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_fingerprint(token)))
    if row is None or row.expires_at <= now:
        return False
    if now - row.last_seen_at >= LAST_SEEN_STEP:
        row.last_seen_at = now
        db.commit()
    return True


def delete_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_fingerprint(token)))
        db.commit()


@dataclass
class LoginThrottle:
    """Counts wrong passwords and blocks sign-in for a while after too many.

    One counter for the whole app (it has one user): behind Tailscale or a
    proxy every request seems to come from the same address anyway. Kept in
    memory: a restart resets it, which is fine for a personal app.
    """

    max_failures: int = 5
    window: timedelta = timedelta(minutes=15)
    lock: timedelta = timedelta(minutes=15)
    _failures: list[datetime] = field(default_factory=list)
    _locked_until: datetime | None = None

    def retry_after(self, now: datetime) -> int:
        """Seconds to wait before the next try (0 = allowed now)."""
        if self._locked_until is None or now >= self._locked_until:
            return 0
        return int((self._locked_until - now).total_seconds()) + 1

    def record_failure(self, now: datetime) -> None:
        self._failures = [t for t in self._failures if now - t < self.window] + [now]
        if len(self._failures) >= self.max_failures:
            self._locked_until = now + self.lock
            self._failures = []

    def record_success(self) -> None:
        self._failures = []
        self._locked_until = None
