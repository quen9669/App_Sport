"""Raw payloads exactly as received from external APIs.

Why keep them? If we later discover a mapping bug or want a new field, we can
rebuild the normalised tables from these rows without calling the API again
(Strava quotas are tight).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class RawPayload(Base):
    __tablename__ = "raw_payload"
    # Replaying a sync overwrites the same row instead of adding a duplicate.
    __table_args__ = (UniqueConstraint("source", "kind", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    # What the payload is: "activity", "activity_streams", "athlete_zones", "sleep"...
    kind: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[Any] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
