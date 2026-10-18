"""Places where activities without GPS happen (gyms, mostly).

A gym session has no GPS route. To still show it on the map and the heatmap,
it is placed at a known place: one chosen by hand for that activity, else the
default place for its kind (strength sessions or everything else).
"""

from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class Place(Base):
    __tablename__ = "place"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    # Default place for activities without GPS, see app.services.places.PlaceRole:
    # "strength_default", "other_default", or None. At most one place per role.
    role: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
