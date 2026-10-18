"""Bookkeeping of synchronisations: a journal of runs, and where each one stopped."""

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class SyncLog(Base):
    """One row per synchronisation run, shown on the "Sources" screen."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # see SyncKind
    status: Mapped[str] = mapped_column(String(16))  # see SyncStatus
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    items_created: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    # Short, secret-free error description when something went wrong.
    error: Mapped[str | None] = mapped_column(Text)


class SyncCursor(Base):
    """Remembers progress of a long job, e.g. the Strava history import.

    ``name`` identifies the job ("strava_backfill") and ``value`` holds its
    position as text (for Strava: the timestamp of the oldest activity reached).
    If the job stops, the next run continues from ``value``.
    """

    __tablename__ = "sync_cursor"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(255))
    completed: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
