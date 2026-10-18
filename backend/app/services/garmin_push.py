"""Send a run of the accepted weekly plan to Garmin Connect, or take it back.

FRANKS chooses which sessions go to his watch: nothing is sent automatically.
Once sent, the session keeps the Garmin ids in the plan (``session["garmin"]``)
so that "Retirer" removes exactly what the app created, and nothing else.
"""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CoachPlan
from app.integrations.health import garmin_workouts
from app.integrations.health.garmin_workouts import GarminWorkoutApi
from app.services.workouts import RunWorkout, garmin_payload


class PushError(Exception):
    """A request that cannot be done; the message is shown to FRANKS (French)."""


def _session(plan: CoachPlan, index: int) -> dict[str, Any]:
    if plan.status != "accepted":
        raise PushError("Accepte d’abord ce plan sur l’écran du coach.")
    if not 0 <= index < len(plan.days):
        raise PushError("Cette séance n’existe pas.")
    session = plan.days[index]
    if session.get("kind") != "run" or not session.get("workout"):
        raise PushError("Seules les séances de course avec leurs étapes vont sur la montre.")
    return session


def _save(db: Session, plan: CoachPlan, index: int, session: dict[str, Any]) -> None:
    # A new list (not an edit in place) so SQLAlchemy sees that the JSON changed.
    days = list(plan.days)
    days[index] = session
    plan.days = days
    db.commit()


def update_workout(db: Session, plan: CoachPlan, index: int, workout: RunWorkout) -> None:
    """Replace the steps of a run (edited on the Mon plan page)."""
    session = _session(plan, index)
    if session.get("garmin"):
        raise PushError("Retire d’abord la séance de ta Garmin, puis modifie-la.")
    _save(db, plan, index, {**session, "workout": workout.model_dump(mode="json")})


def push(
    db: Session,
    plan: CoachPlan,
    index: int,
    login: Callable[[], GarminWorkoutApi],
    targets: dict[str, tuple[float, float]],
    today: date,
    now: datetime,
) -> None:
    """Create the workout on Garmin Connect and put it on the session's day."""
    session = _session(plan, index)
    if session.get("garmin"):
        raise PushError("Cette séance est déjà sur ta Garmin.")
    day = date.fromisoformat(session["day"])
    if day < today:
        raise PushError("Cette séance est passée : elle ne part plus sur la montre.")
    workout = RunWorkout.model_validate(session["workout"])
    payload = garmin_payload(session["title"], workout, targets, session.get("details", ""))
    workout_id, scheduled_id = garmin_workouts.create_and_schedule(
        login(), payload, day.isoformat()
    )
    garmin = {"workout_id": workout_id, "scheduled_id": scheduled_id, "sent_at": now.isoformat()}
    _save(db, plan, index, {**session, "garmin": garmin})


def remove(db: Session, plan: CoachPlan, index: int, login: Callable[[], GarminWorkoutApi]) -> None:
    """Delete from Garmin Connect the workout this app created for the session."""
    session = _session(plan, index)
    garmin = session.get("garmin")
    if not garmin:
        raise PushError("Cette séance n’est pas sur ta Garmin.")
    garmin_workouts.remove(login(), int(garmin["workout_id"]), garmin.get("scheduled_id"))
    _save(db, plan, index, {key: value for key, value in session.items() if key != "garmin"})
