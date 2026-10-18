"""Smoke-free tracking: the days FRANKS smoked a cigarette after quitting.

Only the exceptions are stored (one row per day with a cigarette): every other
day since the quit date is a smoke-free day. Vaping is not tracked here, only
cigarettes. Kept as plain daily data so a future "longévité" screen can use it.
The quit date itself is ``UserProfile.smoke_free_since``.
"""

from datetime import date, datetime

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class SmokingDay(Base):
    __tablename__ = "smoking_day"

    id: Mapped[int] = mapped_column(primary_key=True)
    # A local calendar day (Europe/Luxembourg), not a moment: no timezone here.
    day: Mapped[date] = mapped_column(Date, unique=True, index=True)
    cigarettes: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(500))  # e.g. "soirée entre amis"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
