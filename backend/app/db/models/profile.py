"""The single user's profile. Only timezone and units for now; phase 2 adds the rest."""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Luxembourg")
    unit_system: Mapped[str] = mapped_column(String(16), default="metric")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
