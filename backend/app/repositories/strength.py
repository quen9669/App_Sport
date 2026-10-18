"""Database access for strength sessions and their sets."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import StrengthSession, StrengthSet


def list_sessions(db: Session, limit: int) -> list[StrengthSession]:
    """Most recent first. selectinload: fetch all their sets in one extra query."""
    query = (
        select(StrengthSession)
        .options(selectinload(StrengthSession.sets))
        .order_by(StrengthSession.performed_at.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def sessions_between(db: Session, start: datetime, end: datetime) -> list[StrengthSession]:
    query = (
        select(StrengthSession)
        .options(selectinload(StrengthSession.sets))
        .where(StrengthSession.performed_at >= start, StrengthSession.performed_at < end)
        .order_by(StrengthSession.performed_at)
    )
    return list(db.scalars(query))


def get_session(db: Session, session_id: int) -> StrengthSession | None:
    return db.get(StrengthSession, session_id)


def save_session(
    db: Session,
    session: StrengthSession,
    fields: dict[str, Any],
    sets: list[dict[str, Any]],
) -> StrengthSession:
    """Write the session's fields and replace all its sets."""
    for name, value in fields.items():
        setattr(session, name, value)
    session.sets = [StrengthSet(**values) for values in sets]
    if session.id is None:
        db.add(session)
    db.flush()
    return session


def session_linked_to(db: Session, activity_id: int) -> StrengthSession | None:
    return db.scalar(select(StrengthSession).where(StrengthSession.activity_id == activity_id))


def latest_sets_by_exercise(db: Session) -> dict[str, StrengthSet]:
    """For each exercise ever done, its most recent set (the default load to propose).

    "Most recent" = in the latest session containing that exercise, the last set
    typed. Done in Python over a small subquery: a personal history is at most
    a few thousand sets.
    """
    latest_session = (
        select(StrengthSet.exercise, func.max(StrengthSession.performed_at).label("last"))
        .join(StrengthSession)
        .group_by(StrengthSet.exercise)
        .subquery()
    )
    query = (
        select(StrengthSet)
        .join(StrengthSession)
        .join(
            latest_session,
            (latest_session.c.exercise == StrengthSet.exercise)
            & (latest_session.c.last == StrengthSession.performed_at),
        )
        .order_by(StrengthSet.position)
    )
    result: dict[str, StrengthSet] = {}
    for strength_set in db.scalars(query):
        result[strength_set.exercise] = strength_set  # later positions overwrite earlier ones
    return result
