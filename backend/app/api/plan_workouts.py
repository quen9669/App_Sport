"""Runs of the accepted plan: edit their steps, send them to Garmin, take them back.

Thin routes: the rules live in ``services/garmin_push.py``. Every answer is the
updated plan, so the Mon plan page simply redraws it.
"""

from collections.abc import Callable
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.coach import PlanOut
from app.coach.plans import plan_data
from app.config import Settings, get_settings
from app.db.models import CoachPlan
from app.db.session import get_db
from app.dependencies import get_now
from app.integrations.health.garmin_workouts import GarminWorkoutApi
from app.integrations.health.provider import HealthProviderError
from app.repositories import coach as coach_repo
from app.services import garmin_push
from app.services.garmin_push import PushError
from app.services.jobs import garmin_login_once, is_garmin_configured
from app.services.race.predictor import race_report
from app.services.weeks import local_today
from app.services.workouts import RunWorkout, pace_targets

router = APIRouter(prefix="/coach/plans", tags=["coach"])

GarminLogin = Callable[[], GarminWorkoutApi]


def get_garmin_workout_login(settings: Settings = Depends(get_settings)) -> GarminLogin | None:
    """Logs in to Garmin when called (None without credentials). Tests replace it."""
    if not is_garmin_configured(settings):
        return None
    # The real library client has the workout methods too.
    return cast(GarminLogin, garmin_login_once(settings))


def _plan(db: Session, plan_id: int) -> CoachPlan:
    plan = coach_repo.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    return plan


def _require_login(login: GarminLogin | None) -> GarminLogin:
    if login is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Garmin n’est pas configuré (page Sources).")
    return login


def _garmin_failed() -> HTTPException:
    # 502 = the app works but Garmin did not; the library may have broken.
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        "Garmin Connect n’a pas répondu comme prévu. Réessaie plus tard ; "
        "si ça dure, la bibliothèque Garmin a peut-être changé.",
    )


@router.put("/{plan_id}/sessions/{index}/workout", response_model=PlanOut)
def update_session_workout(
    plan_id: int, index: int, workout: RunWorkout, db: Session = Depends(get_db)
) -> PlanOut:
    """Save the steps of a run, edited on the Mon plan page."""
    plan = _plan(db, plan_id)
    try:
        garmin_push.update_workout(db, plan, index, workout)
    except PushError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return PlanOut.model_validate(plan_data(plan))


@router.post("/{plan_id}/sessions/{index}/garmin", response_model=PlanOut)
def send_session_to_garmin(
    plan_id: int,
    index: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    login: GarminLogin | None = Depends(get_garmin_workout_login),
    now: datetime = Depends(get_now),
) -> PlanOut:
    """Create the run on Garmin Connect, on its day: the watch gets it at its next sync."""
    plan = _plan(db, plan_id)
    targets = pace_targets(race_report(db, settings.app_timezone, now).zones)
    try:
        garmin_push.push(
            db,
            plan,
            index,
            _require_login(login),
            targets,
            local_today(settings.app_timezone, now),
            now,
        )
    except PushError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except HealthProviderError:
        raise _garmin_failed() from None
    return PlanOut.model_validate(plan_data(plan))


@router.delete("/{plan_id}/sessions/{index}/garmin", response_model=PlanOut)
def remove_session_from_garmin(
    plan_id: int,
    index: int,
    db: Session = Depends(get_db),
    login: GarminLogin | None = Depends(get_garmin_workout_login),
) -> PlanOut:
    """Delete from Garmin Connect the workout the app created for this run."""
    plan = _plan(db, plan_id)
    try:
        garmin_push.remove(db, plan, index, _require_login(login))
    except PushError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except HealthProviderError:
        raise _garmin_failed() from None
    return PlanOut.model_validate(plan_data(plan))
