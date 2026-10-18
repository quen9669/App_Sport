"""Database access for stored (encrypted) credentials."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SourceCredential


def get_credential(db: Session, source: str) -> SourceCredential | None:
    return db.scalar(select(SourceCredential).where(SourceCredential.source == source))


def delete_credential(db: Session, source: str) -> None:
    credential = get_credential(db, source)
    if credential is not None:
        db.delete(credential)
        db.commit()
