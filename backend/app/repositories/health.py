"""Database access for sleep nights and daily health metrics."""

from dataclasses import asdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DailyHealth, SleepNight
from app.integrations.health.provider import DailyHealthRecord, SleepRecord

# Fields of the records that are not database columns.
_NOT_COLUMNS = {"raw", "night_date", "day"}


def upsert_sleep(db: Session, source: str, record: SleepRecord) -> bool:
    """Insert or update the night (unique per source and date). Returns True if created."""
    row = db.scalar(
        select(SleepNight).where(
            SleepNight.source == source, SleepNight.night_date == record.night_date
        )
    )
    created = row is None
    if row is None:
        row = SleepNight(source=source, night_date=record.night_date)
        db.add(row)
    for name, value in asdict(record).items():
        if name not in _NOT_COLUMNS:
            setattr(row, name, value)
    return created


def upsert_daily(db: Session, source: str, record: DailyHealthRecord) -> bool:
    row = db.scalar(
        select(DailyHealth).where(DailyHealth.source == source, DailyHealth.day == record.day)
    )
    created = row is None
    if row is None:
        row = DailyHealth(source=source, day=record.day)
        db.add(row)
    for name, value in asdict(record).items():
        if name not in _NOT_COLUMNS:
            setattr(row, name, value)
    return created


def latest_night(db: Session, source: str) -> date | None:
    return db.scalar(select(func.max(SleepNight.night_date)).where(SleepNight.source == source))


def latest_day(db: Session, source: str) -> date | None:
    return db.scalar(select(func.max(DailyHealth.day)).where(DailyHealth.source == source))


def count_nights(db: Session, source: str | None = None) -> int:
    query = select(func.count()).select_from(SleepNight)
    if source is not None:
        query = query.where(SleepNight.source == source)
    return db.scalar(query) or 0


def count_days(db: Session, source: str | None = None) -> int:
    query = select(func.count()).select_from(DailyHealth)
    if source is not None:
        query = query.where(DailyHealth.source == source)
    return db.scalar(query) or 0


def resting_heartrates_since(db: Session, since: date) -> list[int]:
    """Daily resting heart rates (any source) from ``since`` to today."""
    query = select(DailyHealth.resting_heartrate).where(
        DailyHealth.day >= since, DailyHealth.resting_heartrate.is_not(None)
    )
    return [value for value in db.scalars(query) if value is not None]
