"""Map screen: activity routes (filtered, simplified) and the places of gym sessions."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.types import utc_now
from app.services import geo
from app.services.activity_map import MapFilters, SportGroup, map_routes, sport_group

router = APIRouter(prefix="/map", tags=["map"])


class MapRouteOut(BaseModel):
    id: int
    name: str
    sport_type: str
    sport: SportGroup  # run / ride / other, for the colour and the filter
    start_time: datetime
    distance_m: float | None
    moving_time_s: int | None
    elapsed_time_s: int
    elevation_gain_m: float | None
    average_speed_mps: float | None
    average_heartrate: float | None
    polyline: str  # encoded, simplified for the zoom level


class PlaceActivityOut(BaseModel):
    id: int
    name: str
    sport: SportGroup
    start_time: datetime
    elapsed_time_s: int


class MapPlaceOut(BaseModel):
    """A place where activities without GPS happened (e.g. a gym)."""

    id: int
    name: str
    latitude: float
    longitude: float
    activity_count: int
    activities: list[PlaceActivityOut]  # the most recent ones, newest first


# A popup lists the latest sessions only; the count says how many there are.
PLACE_ACTIVITIES_SHOWN = 5


class BoundsOut(BaseModel):
    south: float
    west: float
    north: float
    east: float


class MapRoutesOut(BaseModel):
    routes: list[MapRouteOut]  # oldest first: recent routes are drawn on top
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
    return MapRoutesOut(
        routes=[
            MapRouteOut(
                id=item.activity.id,
                name=item.activity.name,
                sport_type=item.activity.sport_type,
                sport=sport_group(item.activity),
                start_time=item.activity.start_time,
                distance_m=item.activity.distance_m,
                moving_time_s=item.activity.moving_time_s,
                elapsed_time_s=item.activity.elapsed_time_s,
                elevation_gain_m=item.activity.elevation_gain_m,
                average_speed_mps=item.activity.average_speed_mps,
                average_heartrate=item.activity.average_heartrate,
                polyline=item.polyline,
            )
            for item in result.routes
        ],
        places=[
            MapPlaceOut(
                id=item.place.id,
                name=item.place.name,
                latitude=item.place.latitude,
                longitude=item.place.longitude,
                activity_count=len(item.activities),
                activities=[
                    PlaceActivityOut(
                        id=activity.id,
                        name=activity.name,
                        sport=sport_group(activity),
                        start_time=activity.start_time,
                        elapsed_time_s=activity.elapsed_time_s,
                    )
                    for activity in item.activities[:PLACE_ACTIVITIES_SHOWN]
                ],
            )
            for item in result.places
        ],
        bounds=BoundsOut(**vars(result.bounds)) if result.bounds else None,
        total=result.total,
    )
