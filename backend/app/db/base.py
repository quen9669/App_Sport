"""Base class shared by every database model.

All models inherit from :class:`Base`. Alembic reads ``Base.metadata`` to know
which tables exist and to generate migrations.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Give every constraint and index a predictable name. Without this, SQLite and
# PostgreSQL invent different names, and later migrations that drop or alter a
# constraint break on one of the two databases.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent of all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
