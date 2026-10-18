"""Strength sessions typed in the app: the exercises, sets, reps and loads.

Strava only knows "WeightTraining, 1 h"; what was actually lifted is entered
here, set by set, at the gym.
"""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class StrengthSession(Base):
    __tablename__ = "strength_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    performed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    # Optional link to the Strava activity of the same session. A linked session
    # is counted once, through its activity (no double counting in goals).
    # ondelete="SET NULL": deleting the activity keeps the typed sets.
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activity.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    # cascade + delete-orphan: deleting a session deletes its sets, and removing
    # a set from this list deletes it from the database.
    sets: Mapped[list["StrengthSet"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="StrengthSet.position",
    )


class StrengthSet(Base):
    __tablename__ = "strength_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("strength_session.id", ondelete="CASCADE"), index=True
    )
    # Order of the set in the whole session (0, 1, 2...), to show them as typed.
    position: Mapped[int] = mapped_column(Integer)
    # The exercise's French name, from the catalogue (app/services/exercises.py)
    # or typed freely. Stored as text so a renamed catalogue never breaks history.
    exercise: Mapped[str] = mapped_column(String(64), index=True)
    set_number: Mapped[int] = mapped_column(Integer)  # 1, 2, 3... within the exercise
    reps: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)  # None = body weight only
    rpe: Mapped[int | None] = mapped_column(Integer)  # perceived effort, 1 (easy) to 10 (max)

    session: Mapped[StrengthSession] = relationship(back_populates="sets")
