"""OAuth tokens of external services, stored **encrypted**.

The columns ending in ``_encrypted`` contain ciphertext produced by
``app.services.crypto.TokenCipher``. Reading the database file alone is not
enough to use the tokens: the key lives in ``.env``, outside the database.
"""

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class SourceCredential(Base):
    __tablename__ = "source_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    # One row per source ("strava", "garmin"), hence unique.
    source: Mapped[str] = mapped_column(String(32), unique=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Permissions actually granted by the user, e.g. "read,activity:read_all".
    scope: Mapped[str | None] = mapped_column(String(255))
    # Id of the account on the external service (Strava athlete id), useful for display.
    external_account_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
