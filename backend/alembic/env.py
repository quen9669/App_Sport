"""Alembic migration environment.

Alembic compares our models (``Base.metadata``) with the database and writes
migration scripts in ``alembic/versions/``. Each script moves the schema one
step forward (``upgrade``) or back (``downgrade``).

Common commands (from ``backend/``, or through make):
- ``uv run alembic upgrade head``: bring the database up to date (``make db-upgrade``)
- ``uv run alembic revision --autogenerate -m "add goal table"``: create a new migration
"""

from logging.config import fileConfig
from typing import Any

from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection

import app.db.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from app.config import get_settings
from app.db.base import Base
from app.db.session import build_engine
from app.db.types import UTCDateTime

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Tests pass their own URL with `config.set_main_option("sqlalchemy.url", ...)`.
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    """Write our custom UTCDateTime as a plain ``sa.DateTime(timezone=True)`` in migrations.

    Migrations must not import application code: it changes over time, while a
    migration has to keep working exactly as written.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False  # False = let Alembic render everything else as usual.


def _configure(connection: Connection | None = None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        # SQLite cannot ALTER most column properties; "batch mode" makes Alembic
        # recreate the table instead, transparently. Harmless on PostgreSQL.
        render_as_batch=True,
        compare_type=True,
        render_item=_render_item,
    )


def run_migrations_offline() -> None:
    """Generate SQL without connecting (``alembic upgrade head --sql``)."""
    _configure(url=_database_url())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to the real database."""
    engine = build_engine(_database_url())
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
