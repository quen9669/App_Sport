"""Health of the app itself, for the "Monitoring" settings page.

Read-only and technical only: sync runs, nightly copies, database size,
coach spending and the container's memory. Never any health data (sleep,
weight, heart rate...) and never a position: this page answers "is the app
working?", not "how am I doing?".

Each check gets a ``status``:
- ``ok``: nothing to do;
- ``warning``: worth a look (a sync late, memory getting high...);
- ``error``: something is broken (no successful sync for half a day...);
- ``unknown``: not measurable here (no cgroup outside Docker, no copy yet...).

The thresholds are module constants so the page and the tests agree on them.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coach.costs import month_budget
from app.config import Settings
from app.db.models.activity import Activity
from app.db.models.enums import DataSource, SyncStatus
from app.db.models.sync import SyncLog
from app.services.backup import PREFIX, list_backups, sqlite_path

Status = Literal["ok", "warning", "error", "unknown"]

# Syncs run every SYNC_INTERVAL_HOURS (3 h by default): two missed runs is a
# warning, four is an error. "partial" (stopped by Strava's quota, resumes on
# the next run) counts as a success: the data did arrive.
SYNC_WARNING_HOURS = 6
SYNC_ERROR_HOURS = 12
# The copy is made every night at 03:30: one missed night is an error.
BACKUP_ERROR_HOURS = 30
# Docker stops the app when it reaches its memory limit.
MEMORY_WARNING_SHARE = 0.85
# How far back the failed runs are counted.
FAILURE_WINDOW = timedelta(days=7)

# Where Docker (cgroup v2) shows the container's own memory use and limit.
CGROUP_DIR = Path("/sys/fs/cgroup")

# When this Python process started: the app's "up since".
PROCESS_STARTED_AT = datetime.now(UTC)

MONITORED_SOURCES = (DataSource.GARMIN, DataSource.STRAVA)
_GOOD_RUNS = (SyncStatus.SUCCESS, SyncStatus.PARTIAL)


@dataclass(frozen=True)
class SourceHealth:
    source: str
    status: Status
    last_success_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    last_error: str | None
    failures_7d: int


@dataclass(frozen=True)
class BackupHealth:
    status: Status
    last_copy_at: datetime | None
    copies: int
    last_copy_bytes: int | None


@dataclass(frozen=True)
class MemoryHealth:
    status: Status
    used_bytes: int | None
    limit_bytes: int | None


@dataclass(frozen=True)
class CoachHealth:
    status: Status
    enabled: bool
    month: str
    spent_eur: float
    limit_eur: float


@dataclass(frozen=True)
class Monitoring:
    status: Status
    checked_at: datetime
    started_at: datetime
    sources: list[SourceHealth]
    backup: BackupHealth
    memory: MemoryHealth
    coach: CoachHealth
    database_bytes: int | None
    activities_7d: int


def _hours_since(moment: datetime | None, now: datetime) -> float | None:
    return None if moment is None else (now - moment).total_seconds() / 3600


def source_health(db: Session, source: str, now: datetime) -> SourceHealth:
    """Last run, last good run and recent failures of one sync source."""
    last_run = db.scalar(
        select(SyncLog).where(SyncLog.source == source).order_by(SyncLog.started_at.desc())
    )
    last_good = db.scalar(
        select(func.max(SyncLog.started_at)).where(
            SyncLog.source == source, SyncLog.status.in_(_GOOD_RUNS)
        )
    )
    failures = db.scalar(
        select(func.count()).where(
            SyncLog.source == source,
            SyncLog.status == SyncStatus.FAILED,
            SyncLog.started_at >= now - FAILURE_WINDOW,
        )
    )
    age = _hours_since(last_good, now)
    status: Status
    if last_run is None:
        status = "unknown"  # never synced: not configured, not "broken"
    elif age is None or age > SYNC_ERROR_HOURS:
        status = "error"
    elif age > SYNC_WARNING_HOURS or last_run.status == SyncStatus.FAILED:
        status = "warning"
    else:
        status = "ok"
    return SourceHealth(
        source=source,
        status=status,
        last_success_at=last_good,
        last_run_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
        # The journal only ever holds short, secret-free messages; cut anyway.
        last_error=last_run.error[:300] if last_run and last_run.error else None,
        failures_7d=int(failures or 0),
    )


def _copy_time(path: Path) -> datetime | None:
    """The UTC time written in a copy's name (app_sport-20261018-033000.db)."""
    stamp = path.stem.removeprefix(PREFIX)
    for pattern in ("%Y%m%d-%H%M%S", "%Y%m%d-%H%M"):
        try:
            return datetime.strptime(stamp, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def backup_health(backup_dir: Path, now: datetime) -> BackupHealth:
    """The nightly copies kept next to the database (the Drive upload is separate)."""
    copies = list_backups(backup_dir)
    if not copies:
        return BackupHealth("unknown", None, 0, None)
    last_at = _copy_time(copies[0])
    age = _hours_since(last_at, now)
    status: Status = "ok" if age is not None and age <= BACKUP_ERROR_HOURS else "error"
    return BackupHealth(status, last_at, len(copies), copies[0].stat().st_size)


def _read_int(path: Path) -> int | None:
    """A number from a cgroup file; None when missing or "max" (no limit)."""
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def memory_health(cgroup_dir: Path = CGROUP_DIR) -> MemoryHealth:
    """The container's memory use against its Docker limit (512 MB on the VPS).

    Outside Docker (development on the PC) there is no such file: ``unknown``.
    """
    used = _read_int(cgroup_dir / "memory.current")
    limit = _read_int(cgroup_dir / "memory.max")
    if used is None:
        return MemoryHealth("unknown", None, None)
    if limit is None:
        return MemoryHealth("ok", used, None)
    status: Status = "warning" if used >= limit * MEMORY_WARNING_SHARE else "ok"
    return MemoryHealth(status, used, limit)


def coach_health(db: Session, now: datetime, settings: Settings) -> CoachHealth:
    budget = month_budget(db, now, settings)
    status: Status
    if budget.exhausted:
        status = "error"
    elif budget.warning:
        status = "warning"
    else:
        status = "ok"
    return CoachHealth(
        status=status,
        enabled=settings.provider is not None,
        month=budget.month,
        spent_eur=round(budget.spent_eur, 2),
        limit_eur=budget.limit_eur,
    )


def database_bytes(database_url: str) -> int | None:
    path = sqlite_path(database_url)
    return path.stat().st_size if path is not None and path.is_file() else None


def activities_last_week(db: Session, now: datetime) -> int:
    """Activities the syncs added in the last 7 days (a sign they bring data)."""
    count = db.scalar(select(func.count()).where(Activity.created_at >= now - timedelta(days=7)))
    return int(count or 0)


def overall(statuses: list[Status]) -> Status:
    """The worst status wins; "unknown" never raises the alarm on its own."""
    if "error" in statuses:
        return "error"
    return "warning" if "warning" in statuses else "ok"


def monitoring(
    db: Session,
    settings: Settings,
    now: datetime | None = None,
    cgroup_dir: Path = CGROUP_DIR,
) -> Monitoring:
    """Everything the Monitoring page shows, computed in a few small queries."""
    now = now or datetime.now(UTC)
    sources = [source_health(db, source, now) for source in MONITORED_SOURCES]
    backup = backup_health(Path(settings.backup_dir), now)
    memory = memory_health(cgroup_dir)
    coach = coach_health(db, now, settings)
    statuses = [s.status for s in sources] + [backup.status, memory.status, coach.status]
    return Monitoring(
        status=overall(statuses),
        checked_at=now,
        started_at=PROCESS_STARTED_AT,
        sources=sources,
        backup=backup,
        memory=memory,
        coach=coach,
        database_bytes=database_bytes(settings.database_url),
        activities_7d=activities_last_week(db, now),
    )
