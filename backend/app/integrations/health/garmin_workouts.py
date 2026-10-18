"""Write workouts to Garmin Connect (unofficial ``garminconnect`` library).

This is the only place where the app WRITES to the Garmin account. It only
ever creates a workout, puts it on one day of the calendar, and later removes
what it created itself (ids kept in the plan). It never lists or deletes
anything else.
"""

from typing import Any, Protocol

from app.integrations.health.garmin_connect import call_garmin
from app.integrations.health.provider import HealthProviderError


class GarminWorkoutApi(Protocol):
    """The methods of ``garminconnect.Garmin`` used here (tests pass a fake)."""

    def upload_workout(self, workout_json: dict[str, Any]) -> dict[str, Any]: ...
    def schedule_workout(self, workout_id: int | str, date_str: str) -> dict[str, Any]: ...
    def unschedule_workout(self, scheduled_workout_id: int | str) -> Any: ...
    def delete_workout(self, workout_id: int | str) -> Any: ...


def _id(answer: Any, *keys: str) -> int:
    """The first id found in Garmin's answer, or an error if the answer changed shape."""
    if isinstance(answer, dict):
        for key in keys:
            value = answer.get(key)
            if isinstance(value, int) and value > 0:
                return value
    raise HealthProviderError("Garmin answered without the expected id")


def create_and_schedule(
    api: GarminWorkoutApi, payload: dict[str, Any], day: str
) -> tuple[int, int | None]:
    """Create the workout, then put it on ``day`` (YYYY-MM-DD) in the calendar.

    Returns (workout id, calendar entry id). If scheduling fails, the new workout
    is deleted again so nothing half-made stays on the account.
    """
    workout_id = _id(call_garmin(api.upload_workout, payload), "workoutId")
    try:
        answer = call_garmin(api.schedule_workout, workout_id, day)
    except HealthProviderError:
        call_garmin(api.delete_workout, workout_id)
        raise
    # The calendar id lets us remove the entry; Garmin may not always send it.
    scheduled = answer.get("workoutScheduleId") if isinstance(answer, dict) else None
    return workout_id, scheduled if isinstance(scheduled, int) else None


def remove(api: GarminWorkoutApi, workout_id: int, scheduled_id: int | None) -> None:
    """Take the session off the calendar and delete the workout the app created.

    Already gone on Garmin (deleted by hand on the watch or the website)? Fine:
    ``call_garmin`` turns "not found" into None.
    """
    if scheduled_id is not None:
        call_garmin(api.unschedule_workout, scheduled_id)
    call_garmin(api.delete_workout, workout_id)
