"""Nightly copies of the SQLite database (phase 6).

SQLite's own backup API copies a consistent snapshot even while the app is
writing, unlike a plain file copy. Copies are named by their UTC time
(``app_sport-20261018-0330.db``) and only the most recent ``keep`` stay. They
live outside the repository (``BACKUP_DIR``, default ``backend/data/backups``,
ignored by git) because they hold health data.
"""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

PREFIX = "app_sport-"


def sqlite_path(database_url: str) -> Path | None:
    """The database file, or None for a non-SQLite or in-memory database."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


def backup_database(database_url: str, backup_dir: Path, keep: int, now: datetime) -> Path | None:
    """Write a snapshot of the database and delete the oldest copies beyond ``keep``."""
    source = sqlite_path(database_url)
    if source is None or not source.is_file():
        logger.info("No SQLite database file to back up")
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{PREFIX}{now:%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    for old in list_backups(backup_dir)[keep:]:
        old.unlink()
    logger.info("Database backed up to %s", target.name)
    return target


def list_backups(backup_dir: Path) -> list[Path]:
    """Existing copies, most recent first (the names sort by date)."""
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob(f"{PREFIX}*.db"), reverse=True)


def restore_database(database_url: str, backup: Path) -> Path:
    """Put a copy back in place of the database; the current one is kept aside.

    Run it with the app stopped. Returns where the replaced database was saved.
    """
    target = sqlite_path(database_url)
    if target is None:
        raise ValueError("Restore only works with a SQLite database file.")
    if not backup.is_file():
        raise FileNotFoundError(backup)
    aside = target.with_name(f"{target.name}.before-restore")
    if target.is_file():
        shutil.copy2(target, aside)
    shutil.copy2(backup, target)
    return aside
