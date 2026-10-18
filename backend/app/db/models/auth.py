"""Login sessions (phase 6): one row per device where FRANKS is signed in.

The browser keeps a random token in a cookie; only its SHA-256 fingerprint is
stored here, so a copy of the database never lets anyone sign in. Deleting a
row signs that device out ("Se déconnecter").
"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class AuthSession(Base):
    __tablename__ = "auth_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    # SHA-256 of the cookie token, in hexadecimal (64 characters).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    # "Chrome on Android"...: helps recognise a device; never used for security.
    user_agent: Mapped[str | None] = mapped_column(String(200))
