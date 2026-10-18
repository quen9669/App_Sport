"""Database access for the user profile and body measurements."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BodyMetric, UserProfile
from app.db.models.enums import DataSource

PROFILE_ID = 1  # single-user application: the profile is always row 1


def get_or_create_profile(db: Session) -> UserProfile:
    profile = db.get(UserProfile, PROFILE_ID)
    if profile is None:
        profile = UserProfile(id=PROFILE_ID)
        db.add(profile)
        db.flush()
    return profile


def update_profile(db: Session, fields: dict[str, Any]) -> UserProfile:
    profile = get_or_create_profile(db)
    for name, value in fields.items():
        setattr(profile, name, value)
    db.flush()
    return profile


def list_body_metrics(db: Session, since: date | None = None) -> list[BodyMetric]:
    """Measurements from oldest to newest (the order a chart needs)."""
    query = select(BodyMetric).order_by(BodyMetric.measured_on)
    if since is not None:
        query = query.where(BodyMetric.measured_on >= since)
    return list(db.scalars(query))


def latest_body_metric(db: Session) -> BodyMetric | None:
    return db.scalar(select(BodyMetric).order_by(BodyMetric.measured_on.desc()).limit(1))


def upsert_body_metric(db: Session, measured_on: date, fields: dict[str, Any]) -> BodyMetric:
    """One measurement per day: weighing yourself twice keeps the last value."""
    metric = db.scalar(select(BodyMetric).where(BodyMetric.measured_on == measured_on))
    if metric is None:
        metric = BodyMetric(measured_on=measured_on)
        db.add(metric)
    metric.source = fields.pop("source", DataSource.MANUAL)
    for name, value in fields.items():
        setattr(metric, name, value)
    db.flush()
    return metric


def delete_body_metric(db: Session, metric_id: int) -> bool:
    metric = db.get(BodyMetric, metric_id)
    if metric is None:
        return False
    db.delete(metric)
    db.flush()
    return True
