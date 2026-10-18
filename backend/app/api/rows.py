"""Fields shared by every activity shown as a row of a table (week, map list).

One definition so the "Séances de la semaine" table and the map's table show
the same columns: flag, town, date, name, sport, distance, duration, heart rate.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models import Activity
from app.services.activity_location import Location
from app.services.activity_map import SportGroup, sport_group


class ActivityRowFields(BaseModel):
    id: int
    name: str
    sport: SportGroup  # run / ride / walk / strength / other: emoji and colour
    start_time: datetime
    distance_m: float | None
    moving_time_s: int | None
    elapsed_time_s: int
    city: str | None
    country_code: str | None  # "LU": the frontend turns it into a flag
    average_heartrate: float | None  # bpm, from the watch (None without a HR sensor)
    max_heartrate: float | None


def row_fields(activity: Activity, location: Location) -> dict[str, Any]:
    """Values for :class:`ActivityRowFields` (to unpack with ``**``)."""
    return {
        "id": activity.id,
        "name": activity.name,
        "sport": sport_group(activity),
        "start_time": activity.start_time,
        "distance_m": activity.distance_m,
        "moving_time_s": activity.moving_time_s,
        "elapsed_time_s": activity.elapsed_time_s,
        "city": location.city,
        "country_code": location.country_code,
        "average_heartrate": activity.average_heartrate,
        "max_heartrate": activity.max_heartrate,
    }
