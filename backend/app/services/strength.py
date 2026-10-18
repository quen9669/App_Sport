"""Rules about typed strength sessions that the goals need.

The same gym session can exist twice: as a strength activity recorded by the
watch (Garmin, or Strava) and as a session typed in the app (the sets). It must
count only once. A typed session is therefore counted on its own only when:
- it is not linked to an activity (a link to an activity hidden by hand does
  not count: that activity is ignored everywhere), and
- no visible strength activity started within MATCH_WINDOW of it (the watch recording
  may be synced after the session was typed, so the link can't always exist yet).
"""

from datetime import timedelta

from app.db.models import Activity, StrengthSession
from app.services.classification import Category, effective_category

MATCH_WINDOW = timedelta(hours=3)


def matching_activity(session: StrengthSession, activities: list[Activity]) -> Activity | None:
    """The strength activity that is most likely the same session, if any."""
    candidates = [
        activity
        for activity in activities
        if not activity.hidden
        and effective_category(activity) == Category.STRENGTH
        and abs(activity.start_time - session.performed_at) <= MATCH_WINDOW
    ]
    return min(
        candidates,
        key=lambda activity: abs(activity.start_time - session.performed_at),
        default=None,
    )


def counts_on_its_own(session: StrengthSession, activities: list[Activity]) -> bool:
    """True if the session adds to the goals by itself (see the module docstring)."""
    hidden_ids = {activity.id for activity in activities if activity.hidden}
    linked = session.activity_id is not None and session.activity_id not in hidden_ids
    return not linked and matching_activity(session, activities) is None
