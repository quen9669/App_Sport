"""Places for activities without GPS (gyms): list, add, edit, delete.

Coordinates are checked like any input: a latitude outside -90..90 or a
longitude outside -180..180 is refused (422).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.db.session import get_db
from app.services.places import PlaceRole, set_role

router = APIRouter(prefix="/places", tags=["places"])

Name = Annotated[str, Field(min_length=1, max_length=120)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class PlaceIn(BaseModel):
    name: Name
    latitude: Latitude
    longitude: Longitude
    role: PlaceRole | None = None


class PlaceUpdate(BaseModel):
    # Every field is optional: only what is sent changes. "role": null removes the role.
    name: Name | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    role: PlaceRole | None = None


class PlaceOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    role: PlaceRole | None
    chosen_count: int  # activities placed here by hand


def _out(db: Session, place: Place) -> PlaceOut:
    chosen = db.scalar(select(func.count()).where(Activity.place_id == place.id)) or 0
    return PlaceOut(
        id=place.id,
        name=place.name,
        latitude=place.latitude,
        longitude=place.longitude,
        role=PlaceRole(place.role) if place.role else None,
        chosen_count=chosen,
    )


def _get(db: Session, place_id: int) -> Place:
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Place not found")
    return place


@router.get("", response_model=list[PlaceOut])
def list_places(db: Session = Depends(get_db)) -> list[PlaceOut]:
    return [_out(db, place) for place in db.scalars(select(Place).order_by(Place.name))]


@router.post("", response_model=PlaceOut, status_code=status.HTTP_201_CREATED)
def create_place(payload: PlaceIn, db: Session = Depends(get_db)) -> PlaceOut:
    place = Place(name=payload.name, latitude=payload.latitude, longitude=payload.longitude)
    db.add(place)
    db.flush()
    set_role(db, place, payload.role)
    db.commit()
    return _out(db, place)


@router.patch("/{place_id}", response_model=PlaceOut)
def update_place(place_id: int, payload: PlaceUpdate, db: Session = Depends(get_db)) -> PlaceOut:
    place = _get(db, place_id)
    fields = payload.model_dump(exclude_unset=True)
    for name in ("name", "latitude", "longitude"):
        if fields.get(name) is not None:
            setattr(place, name, fields[name])
    if "role" in fields:
        set_role(db, place, payload.role)
    db.commit()
    return _out(db, place)


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_place(place_id: int, db: Session = Depends(get_db)) -> None:
    """Activities placed here by hand go back to their default place."""
    place = _get(db, place_id)
    # Done here as well as by the foreign key (ON DELETE SET NULL), so it does
    # not depend on SQLite having foreign keys switched on.
    db.execute(update(Activity).where(Activity.place_id == place.id).values(place_id=None))
    db.delete(place)
    db.commit()
