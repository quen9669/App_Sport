"""Weekly goals, e.g. "3 strength sessions per week"."""

from datetime import date, datetime

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class Goal(Base):
    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(primary_key=True)
    # What is counted, see app.services.goals.GoalKind:
    # strength_sessions, cardio_sessions, active_minutes, distance_km, training_load,
    # intensity_minutes.
    kind: Mapped[str] = mapped_column(String(32))
    target: Mapped[float] = mapped_column(Float)
    # Only for distance goals: "run", "ride" or None (all sports).
    sport: Mapped[str | None] = mapped_column(String(16))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/paused/done
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
