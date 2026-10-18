"""The single user's profile (one row, id = 1) and body measurements over time."""

from datetime import date, datetime

from sqlalchemy import Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class UserProfile(Base):
    """Personal data used to personalise charts, goals and (later) the coaches.

    Age is not stored: it is computed from ``birth_date``, otherwise it would
    silently become wrong after the next birthday.
    """

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Luxembourg")
    unit_system: Mapped[str] = mapped_column(String(16), default="metric")
    height_cm: Mapped[float | None] = mapped_column(Float)
    sex: Mapped[str | None] = mapped_column(String(16))  # "male", "female", "other"
    birth_date: Mapped[date | None] = mapped_column(Date)
    max_heartrate: Mapped[int | None] = mapped_column(Integer)
    resting_heartrate: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str | None] = mapped_column(String(16))  # beginner/intermediate/advanced
    # Free text: injuries and limitations the coaches must respect.
    injuries: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class BodyMetric(Base):
    """One body measurement per day: an entry on the same day replaces the previous one."""

    __tablename__ = "body_metric"

    id: Mapped[int] = mapped_column(primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, unique=True, index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
