"""Map screen: activity routes (filtered, simplified) and the places of gym sessions."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.rows import ActivityRowFields, row_fields
from app.db.session import get_db
from app.db.types import utc_now
from app.services import geo
from app.services.activity_location import Locator
from app.services.activity_map import MapFilters, SportGroup, map_routes

router = APIRouter(prefix="/map", tags=["map"])


class MapRouteOut(ActivityRowFields):
    sport_type: str
    elevation_gain_m: float | None
    average_speed_mps: float | None
    polyline: str  # encoded, simplified for the zoom level


class MapPointOut(ActivityRowFields):
    """An activity with a start point but no route yet: drawn as a dot."""

    latitude: float
    longitude: float


class PlaceActivityOut(ActivityRowFields):
    pass


class MapPlaceOut(BaseModel):
    """A place where activities without GPS happened (e.g. a gym)."""

    id: int
    name: str
    latitude: float
    longitude: float
    activity_count: int
    activities: list[PlaceActivityOut]  # the most recent ones, newest first


# The list under the map shows at most 30 rows: no need to send more per place.
PLACE_ACTIVITIES_SHOWN = 30


class BoundsOut(BaseModel):
    south: float
    west: float
    north: float
    east: float


class MapRoutesOut(BaseModel):
    routes: list[MapRouteOut]  # oldest first: recent routes are drawn on top
    points: list[MapPointOut]
    places: list[MapPlaceOut]
    bounds: BoundsOut | None  # around every matching route (to frame them all)
    total: int  # matching activities, including those off screen


def _parse_bbox(bbox: str | None) -> geo.Bounds | None:
    """``"west,south,east,north"`` (Leaflet's ``toBBoxString()``) to Bounds."""
    if bbox is None:
        return None
    try:
        west, south, east, north = (float(part) for part in bbox.split(","))
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "bbox must be west,south,east,north"
        ) from None
    return geo.Bounds(south=south, west=west, north=north, east=east)


@router.get("/routes", response_model=MapRoutesOut)
def read_routes(
    sport: SportGroup | None = None,
    days: Annotated[int | None, Query(ge=1, le=36500)] = None,  # None = all the history
    min_km: Annotated[float | None, Query(ge=0, le=1000)] = None,
    max_km: Annotated[float | None, Query(ge=0, le=1000)] = None,
    bbox: str | None = None,  # visible rectangle; None = everything
    zoom: Annotated[float | None, Query(ge=0, le=22)] = None,
    db: Session = Depends(get_db),
) -> MapRoutesOut:
    since = utc_now() - timedelta(days=days) if days is not None else None
    filters = MapFilters(sport=sport, since=since, min_km=min_km, max_km=max_km)
    result = map_routes(db, filters, _parse_bbox(bbox), zoom)
    locator = Locator(db)
    return MapRoutesOut(
        routes=[
            MapRouteOut(
                **row_fields(item.activity, locator.locate(item.activity)),
                sport_type=item.activity.sport_type,
                elevation_gain_m=item.activity.elevation_gain_m,
                average_speed_mps=item.activity.average_speed_mps,
                polyline=item.polyline,
            )
            for item in result.routes
        ],
        points=[
            MapPointOut(
                **row_fields(item.activity, locator.locate(item.activity)),
                latitude=item.latitude,
                longitude=item.longitude,
            )
            for item in result.points
        ],
        places=[
            MapPlaceOut(
                id=item.place.id,
                name=item.place.name,
                latitude=item.place.latitude,
                longitude=item.place.longitude,
                activity_count=len(item.activities),
                activities=[
                    PlaceActivityOut(**row_fields(activity, locator.locate(activity)))
                    for activity in item.activities[:PLACE_ACTIVITIES_SHOWN]
                ],
            )
            for item in result.places
        ],
        bounds=BoundsOut(**vars(result.bounds)) if result.bounds else None,
        total=result.total,
    )
