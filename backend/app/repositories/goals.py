"""Database access for goals."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Goal


def list_goals(db: Session) -> list[Goal]:
    return list(db.scalars(select(Goal).order_by(Goal.id)))


def create_goal(db: Session, fields: dict[str, Any]) -> Goal:
    goal = Goal(**fields)
    db.add(goal)
    db.flush()
    return goal


def update_goal(db: Session, goal: Goal, fields: dict[str, Any]) -> Goal:
    for name, value in fields.items():
        setattr(goal, name, value)
    db.flush()
    return goal
