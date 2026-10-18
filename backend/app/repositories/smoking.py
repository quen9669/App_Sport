"""Database access for the smoke-free tracking (days with a cigarette)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SmokingDay


def list_days(db: Session) -> list[SmokingDay]:
    """Every day with a cigarette, oldest first."""
    return list(db.scalars(select(SmokingDay).order_by(SmokingDay.day)))


def upsert_day(db: Session, day: date, cigarettes: int, note: str | None) -> SmokingDay:
    """One row per day: writing the same day again replaces the count."""
    row = db.scalar(select(SmokingDay).where(SmokingDay.day == day))
    if row is None:
        row = SmokingDay(day=day)
        db.add(row)
    row.cigarettes = cigarettes
    row.note = note
    db.flush()
    return row


def delete_day(db: Session, day: date) -> bool:
    row = db.scalar(select(SmokingDay).where(SmokingDay.day == day))
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True
