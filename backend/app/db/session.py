"""Database engine and sessions.

- The **engine** holds the connection to the database (one per application).
- A **session** is a unit of work: you read and write objects through it, then
  ``commit()`` to save everything at once, or ``rollback()`` to cancel.
"""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def build_engine(database_url: str) -> Engine:
    """Create an engine, with the extra setup SQLite needs."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(database_url, pool_pre_ping=True)

    # SQLite stores the database in a file: make sure its folder exists.
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: FastAPI and the scheduler use several threads.
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        # SQLite ignores foreign keys unless asked; PostgreSQL always enforces them.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the application's session factory, creating the engine on first use.

    Created lazily (not at import time) so that importing the code, e.g. in
    tests, never touches the real database file.
    """
    engine = build_engine(get_settings().database_url)
    # expire_on_commit=False: objects stay readable after commit (handy in API responses).
    return sessionmaker(bind=engine, expire_on_commit=False)


def provide_session_factory() -> sessionmaker[Session]:
    """FastAPI dependency returning the session factory.

    Routes that start background work (which outlives the request) use it to
    open their own session. Tests override this one dependency to point the
    whole app at a temporary database.
    """
    return get_session_factory()


def get_db(
    factory: sessionmaker[Session] = Depends(provide_session_factory),
) -> Iterator[Session]:
    """FastAPI dependency: open a session for one request and always close it.

    Usage in a route: ``def route(db: Session = Depends(get_db)) -> ...``.
    """
    with factory() as session:
        yield session
