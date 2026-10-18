"""Activity routes: the detail of one activity, and corrections by hand (category, hide)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.db.session import get_db
from app.services.activity_map import SportGroup, activity_series, detail_route, sport_group
from app.services.classification import automatic_category, effective_category
from app.services.places import PlaceBook

router = APIRouter(prefix="/activities", tags=["activities"])


class SeriesOut(BaseModel):
    """Aligned series: index ``i`` of each list is the same moment (None = no value)."""

    time_s: list[int]
    distance_m: list[float | None]
    altitude_m: list[float | None]
    heartrate: list[float | None]
    speed_mps: list[float | None]
    latlng: list[list[float] | None]


class ActivityPlaceOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    chosen: bool  # True: chosen by hand; False: the default place for its kind


class ActivityDetailOut(BaseModel):
    id: int
    name: str
    sport_type: str
    sport: SportGroup
    category: str
    source: str
    start_time: datetime
    elapsed_time_s: int
    moving_time_s: int | None
    distance_m: float | None
    elevation_gain_m: float | None
    average_speed_mps: float | None
    max_speed_mps: float | None
    average_heartrate: float | None
    max_heartrate: float | None
    average_cadence: float | None
    hidden: bool
    polyline: str | None  # route for the map, None for indoor sessions
    place: ActivityPlaceOut | None  # only for activities without a route
    series: SeriesOut


@router.get("/{activity_id}", response_model=ActivityDetailOut)
def read_activity(activity_id: int, db: Session = Depends(get_db)) -> ActivityDetailOut:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return _detail(db, activity)


def _detail(db: Session, activity: Activity) -> ActivityDetailOut:
    series = activity_series(activity)
    route = detail_route(series, activity)
    place_out = None
    if route is None:
        place, chosen = PlaceBook(db).locate(activity)
        if place is not None:
            place_out = ActivityPlaceOut(
                id=place.id,
                name=place.name,
                latitude=place.latitude,
                longitude=place.longitude,
                chosen=chosen,
            )
    return ActivityDetailOut(
        id=activity.id,
        name=activity.name,
        sport_type=activity.sport_type,
        sport=sport_group(activity),
        category=effective_category(activity),
        source=activity.source,
        start_time=activity.start_time,
        elapsed_time_s=activity.elapsed_time_s,
        moving_time_s=activity.moving_time_s,
        distance_m=activity.distance_m,
        elevation_gain_m=activity.elevation_gain_m,
        average_speed_mps=activity.average_speed_mps,
        max_speed_mps=activity.max_speed_mps,
        average_heartrate=activity.average_heartrate,
        max_heartrate=activity.max_heartrate,
        average_cadence=activity.average_cadence,
        hidden=activity.hidden,
        polyline=route,
        place=place_out,
        series=SeriesOut(**vars(series)),
    )


class PlaceChoiceIn(BaseModel):
    place_id: int | None  # None = back to the default place for its kind


@router.patch("/{activity_id}/place", response_model=ActivityDetailOut)
def set_place(
    activity_id: int, payload: PlaceChoiceIn, db: Session = Depends(get_db)
) -> ActivityDetailOut:
    """Choose where an activity without GPS happened. Syncs never change it."""
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    if payload.place_id is not None and db.get(Place, payload.place_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Place not found")
    activity.place_id = payload.place_id
    db.commit()
    return _detail(db, activity)


class CategoryIn(BaseModel):
    # None = forget the correction and go back to the automatic rule.
    category: Literal["strength", "cardio", "other"] | None


class CategoryOut(BaseModel):
    id: int
    category: str
    automatic_category: str
    overridden: bool


@router.patch("/{activity_id}/category", response_model=CategoryOut)
def set_category(
    activity_id: int, payload: CategoryIn, db: Session = Depends(get_db)
) -> CategoryOut:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    automatic = automatic_category(activity.sport_type)
    # Choosing the automatic value again is the same as removing the correction.
    activity.category_override = None if payload.category == automatic else payload.category
    db.commit()
    return CategoryOut(
        id=activity.id,
        category=effective_category(activity),
        automatic_category=automatic,
        overridden=activity.category_override is not None,
    )


class HiddenIn(BaseModel):
    hidden: bool


class HiddenOut(BaseModel):
    id: int
    hidden: bool


@router.patch("/{activity_id}/hidden", response_model=HiddenOut)
def set_hidden(activity_id: int, payload: HiddenIn, db: Session = Depends(get_db)) -> HiddenOut:
    """Hide an activity (e.g. one of two possible duplicates), or show it again.

    Nothing is deleted: a hidden activity stays in the database and in the
    week list (greyed out), but no goal or chart counts it.
    """
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    activity.hidden = payload.hidden
    db.commit()
    return HiddenOut(id=activity.id, hidden=activity.hidden)
