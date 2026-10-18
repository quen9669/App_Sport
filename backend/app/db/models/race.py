"""The race FRANKS is preparing (distance, date, target time).

One row at most: the "Course" screen shows a single upcoming race, and the
future coach (phase 5) will read it to tailor its advice.
"""

from datetime import date, datetime

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class RaceTarget(Base):
    __tablename__ = "race_target"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")  # e.g. "Corrida de Noël"
    distance_m: Mapped[float] = mapped_column(Float)
    # A local calendar day, like smoking_day.day: no timezone.
    race_date: Mapped[date] = mapped_column(Date)
    target_time_s: Mapped[int | None] = mapped_column(Integer)  # None = no target, just a plan
    elevation_gain_m: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = flat course
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
