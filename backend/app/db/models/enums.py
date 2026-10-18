"""Fixed lists of values used by several models.

``StrEnum`` values are plain strings in the database ("strava"), which keeps the
data readable with any SQL tool, while the code gets autocompletion and typo checks.
"""

from enum import StrEnum


class DataSource(StrEnum):
    """Where a piece of data comes from."""

    STRAVA = "strava"
    GARMIN = "garmin"
    FILE_IMPORT = "file_import"
    MANUAL = "manual"
    SYNTHETIC = "synthetic"


class SyncKind(StrEnum):
    """Why a synchronisation ran."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    BACKFILL = "backfill"


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"  # stopped early (e.g. rate limit), will resume next run
    FAILED = "failed"
