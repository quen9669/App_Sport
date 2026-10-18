"""Daily health data (Garmin or file import): sleep nights and daily metrics."""

from datetime import date, datetime

from sqlalchemy import Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class SleepNight(Base):
    """One night of sleep. ``night_date`` is the date of the morning you wake up."""

    __tablename__ = "sleep_night"
    __table_args__ = (UniqueConstraint("source", "night_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    night_date: Mapped[date] = mapped_column(Date, index=True)
    sleep_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    sleep_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_s: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)  # 0-100 (Garmin sleep score)
    deep_s: Mapped[int | None] = mapped_column(Integer)
    light_s: Mapped[int | None] = mapped_column(Integer)
    rem_s: Mapped[int | None] = mapped_column(Integer)
    awake_s: Mapped[int | None] = mapped_column(Integer)
    resting_heartrate: Mapped[int | None] = mapped_column(Integer)
    hrv_ms: Mapped[float | None] = mapped_column(Float)  # overnight average HRV
    body_battery_wake: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class DailyHealth(Base):
    """Health metrics summarised per calendar day."""

    __tablename__ = "daily_health"
    __table_args__ = (UniqueConstraint("source", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    day: Mapped[date] = mapped_column(Date, index=True)
    resting_heartrate: Mapped[int | None] = mapped_column(Integer)
    hrv_ms: Mapped[float | None] = mapped_column(Float)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    steps: Mapped[int | None] = mapped_column(Integer)
    vo2max: Mapped[float | None] = mapped_column(Float)
    body_battery_max: Mapped[int | None] = mapped_column(Integer)
    body_battery_min: Mapped[int | None] = mapped_column(Integer)
    # Garmin "intensity minutes" of the day, counted all day long (not only in
    # workouts). Garmin counts a vigorous minute twice in its weekly total.
    intensity_moderate_min: Mapped[int | None] = mapped_column(Integer)
    intensity_vigorous_min: Mapped[int | None] = mapped_column(Integer)
    # Floors climbed and gone down (Garmin counts one floor per ~3 m of height).
    floors_ascended: Mapped[int | None] = mapped_column(Integer)
    floors_descended: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
