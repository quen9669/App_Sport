"""Where an activity happened, for the lists: its town and its country.

- With a GPS start (the source's start point, else the first point of the
  route): the town given by the source and the country of that point.
- Without GPS (gym sessions): the activity's place (see places.py), with the
  town typed on that place and the country of its position.

The country is computed locally (countries.py): no position leaves the app.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Activity
from app.services import polyline
from app.services.countries import country_at
from app.services.places import PlaceBook


@dataclass(frozen=True)
class Location:
    city: str | None
    country_code: str | None  # ISO 3166-1 alpha-2, e.g. "LU"


def start_point(activity: Activity) -> tuple[float, float] | None:
    """(latitude, longitude) where the activity started, if known."""
    if activity.start_latitude is not None and activity.start_longitude is not None:
        return activity.start_latitude, activity.start_longitude
    points = polyline.decode(activity.summary_polyline or "")
    return points[0] if points else None


class Locator:
    """Locates many activities with the places loaded once (one query in all)."""

    def __init__(self, db: Session, book: PlaceBook | None = None) -> None:
        self.book = book or PlaceBook(db)

    def locate(self, activity: Activity) -> Location:
        point = start_point(activity)
        if point is not None:
            return Location(activity.location_name, country_at(*point))
        place, _ = self.book.locate(activity)
        if place is not None:
            return Location(
                activity.location_name or place.city, country_at(place.latitude, place.longitude)
            )
        return Location(activity.location_name, None)
