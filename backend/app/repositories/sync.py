"""Database access for the sync journal (sync_log) and progress markers (sync_cursor)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SyncCursor, SyncLog
from app.db.models.enums import SyncKind, SyncStatus
from app.db.types import utc_now


def start_log(db: Session, source: str, kind: SyncKind) -> SyncLog:
    log = SyncLog(source=source, kind=kind, status=SyncStatus.RUNNING, started_at=utc_now())
    db.add(log)
    db.commit()  # committed right away, so the "running" state is visible to others
    return log


def finish_log(
    db: Session,
    log: SyncLog,
    status: SyncStatus,
    created: int,
    updated: int,
    error: str | None = None,
) -> None:
    log.status = status
    log.items_created = created
    log.items_updated = updated
    log.error = error
    log.finished_at = utc_now()
    db.commit()


def list_logs(db: Session, limit: int = 20, source: str | None = None) -> list[SyncLog]:
    query = select(SyncLog).order_by(SyncLog.started_at.desc(), SyncLog.id.desc()).limit(limit)
    if source is not None:
        query = query.where(SyncLog.source == source)
    return list(db.scalars(query))


def get_cursor(db: Session, name: str) -> SyncCursor:
    """Return the cursor called ``name``, creating an empty one if needed."""
    cursor = db.get(SyncCursor, name)
    if cursor is None:
        cursor = SyncCursor(name=name, value=None, completed=False)
        db.add(cursor)
        db.flush()
    return cursor


def is_cursor_completed(db: Session, name: str) -> bool:
    """Read-only check (unlike :func:`get_cursor`, never creates the row)."""
    cursor = db.get(SyncCursor, name)
    return cursor is not None and cursor.completed
