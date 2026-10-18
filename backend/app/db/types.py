"""Custom column types that behave the same on SQLite and PostgreSQL."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """A datetime column that always stores and returns UTC, timezone-aware values.

    Why: SQLite has no real timezone support and gives back "naive" datetimes
    (without timezone). Mixing naive and aware datetimes raises errors when
    comparing them. This type converts everything to UTC on the way in and
    re-attaches the UTC timezone on the way out. Display in Europe/Luxembourg
    time is the job of the frontend.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime given to a UTCDateTime column; add a timezone.")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utc_now() -> datetime:
    """Current time in UTC (used as default value for timestamp columns)."""
    return datetime.now(UTC)
