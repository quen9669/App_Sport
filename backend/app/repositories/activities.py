"""Database access for activities, their streams and raw payloads."""

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityStream, RawPayload


def upsert_activity(
    db: Session, source: str, external_id: str, fields: dict[str, Any]
) -> tuple[Activity, bool]:
    """Insert the activity, or update it if (source, external_id) already exists.

    This "upsert" is what makes a re-sync idempotent: the same Strava activity
    always lands on the same row. Returns ``(activity, created)``.
    """
    activity = db.scalar(
        select(Activity).where(Activity.source == source, Activity.external_id == external_id)
    )
    created = activity is None
    if activity is None:
        activity = Activity(source=source, external_id=external_id)
        db.add(activity)
    for name, value in fields.items():
        setattr(activity, name, value)
    db.flush()  # sends the INSERT/UPDATE now so that activity.id is known
    return activity, created


def not_duplicate() -> ColumnElement[bool]:
    """SQL condition: the activity is not a confirmed copy of a Garmin one.

    Every list or count of activities uses it (see app/services/dedupe.py).
    Written by hand instead of importing DuplicateStatus to keep this layer
    free of service code; "confirmed" is DuplicateStatus.CONFIRMED.
    """
    return or_(Activity.duplicate_status.is_(None), Activity.duplicate_status != "confirmed")


def activities_between(db: Session, start: datetime, end: datetime) -> list[Activity]:
    """Activities started in [start, end), oldest first, without confirmed duplicates.

    Hidden activities are included (they are listed, greyed out); callers
    that count must skip ``activity.hidden``.
    """
    query = (
        select(Activity)
        .where(Activity.start_time >= start, Activity.start_time < end, not_duplicate())
        .order_by(Activity.start_time)
    )
    return list(db.scalars(query))


def highest_max_heartrate(db: Session, since: datetime, low: int, high: int) -> float | None:
    """Highest max heart rate recorded by an activity since ``since``.

    Readings outside [low, high] are ignored: a strap that slips or a watch
    glitch can report 40 or 250 bpm. Confirmed duplicates and hidden
    activities are skipped, like everywhere else.
    """
    query = select(func.max(Activity.max_heartrate)).where(
        Activity.start_time >= since,
        Activity.max_heartrate.between(low, high),
        Activity.hidden.is_(False),
        not_duplicate(),
    )
    return db.scalar(query)


def upsert_raw_payload(db: Session, source: str, kind: str, external_id: str, payload: Any) -> None:
    """Keep the latest raw JSON for (source, kind, external_id)."""
    row = db.scalar(
        select(RawPayload).where(
            RawPayload.source == source,
            RawPayload.kind == kind,
            RawPayload.external_id == external_id,
        )
    )
    if row is None:
        db.add(RawPayload(source=source, kind=kind, external_id=external_id, payload=payload))
    else:
        row.payload = payload


def save_stream(
    db: Session, activity: Activity, stream_types: list[str], point_count: int, data: bytes
) -> None:
    """Create or replace the stream blob of an activity."""
    stream = db.scalar(select(ActivityStream).where(ActivityStream.activity_id == activity.id))
    if stream is None:
        stream = ActivityStream(activity_id=activity.id)
        db.add(stream)
    stream.stream_types = ",".join(sorted(stream_types))
    stream.point_count = point_count
    stream.data = data


def latest_start_time(db: Session, source: str) -> datetime | None:
    """Start time of the most recent activity from ``source`` (None if there is none)."""
    return db.scalar(select(func.max(Activity.start_time)).where(Activity.source == source))


def activities_missing_streams(db: Session, source: str, limit: int) -> list[Activity]:
    """Activities that should have streams (GPS or heart rate) but don't yet, newest first."""
    query = (
        select(Activity)
        .outerjoin(ActivityStream)
        .where(
            Activity.source == source,
            ActivityStream.id.is_(None),
            Activity.is_manual.is_(False),
            # Don't spend API quota on the details of a copy we never show.
            not_duplicate(),
            (Activity.summary_polyline.is_not(None)) | (Activity.has_heartrate.is_(True)),
        )
        .order_by(Activity.start_time.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def mark_no_streams(db: Session, activity: Activity) -> None:
    """Store an empty stream so we don't ask Strava again for an activity without data."""
    save_stream(db, activity, [], 0, b"")


def count_activities(db: Session, source: str | None = None) -> int:
    query = select(func.count()).select_from(Activity)
    if source is not None:
        query = query.where(Activity.source == source)
    return db.scalar(query) or 0
