"""Database access for the target race (one row at most)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RaceTarget


def get_target(db: Session) -> RaceTarget | None:
    return db.scalar(select(RaceTarget).order_by(RaceTarget.id).limit(1))


def save_target(db: Session, fields: dict[str, Any]) -> RaceTarget:
    """Create the target race, or replace the fields of the existing one."""
    target = get_target(db)
    if target is None:
        target = RaceTarget()
        db.add(target)
    for name, value in fields.items():
        setattr(target, name, value)
    db.flush()
    return target


def delete_target(db: Session) -> None:
    target = get_target(db)
    if target is not None:
        db.delete(target)
        db.flush()
