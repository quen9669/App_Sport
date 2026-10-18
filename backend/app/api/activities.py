"""Activity routes: correct the category of an activity, or hide it, by hand."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Activity
from app.db.session import get_db
from app.services.classification import automatic_category, effective_category

router = APIRouter(prefix="/activities", tags=["activities"])


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
