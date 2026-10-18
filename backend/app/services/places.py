"""Where an activity without GPS happened: a place chosen by hand, else a default.

The owner trains indoors at two gyms (decision 2026-10-18): strength sessions
default to one, every other activity without GPS to the other. A place chosen
by hand on an activity always wins and is never touched by syncs.
"""

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.services.classification import Category, effective_category


class PlaceRole(StrEnum):
    STRENGTH_DEFAULT = "strength_default"  # strength sessions without GPS
    OTHER_DEFAULT = "other_default"  # any other activity without GPS


class PlaceBook:
    """Every place, loaded once, to locate many activities without one query each."""

    def __init__(self, db: Session) -> None:
        places = db.scalars(select(Place)).all()
        self.by_id = {place.id: place for place in places}
        self.by_role = {place.role: place for place in places if place.role}

    def locate(self, activity: Activity) -> tuple[Place | None, bool]:
        """The place of an activity without GPS, and whether it was chosen by hand."""
        if activity.place_id is not None and activity.place_id in self.by_id:
            return self.by_id[activity.place_id], True
        strength = effective_category(activity) == Category.STRENGTH
        role = PlaceRole.STRENGTH_DEFAULT if strength else PlaceRole.OTHER_DEFAULT
        return self.by_role.get(role), False


def set_role(db: Session, place: Place, role: PlaceRole | None) -> None:
    """Make ``place`` the default for ``role`` (taking the role from any other place)."""
    if role is not None:
        for other in db.scalars(select(Place).where(Place.role == role, Place.id != place.id)):
            other.role = None
        db.flush()  # the role column is unique: free it before giving it away
    place.role = role
