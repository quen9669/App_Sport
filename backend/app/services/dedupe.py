"""Recognise the same session recorded in both Garmin Connect and Strava.

Garmin is the main source (it has the heart rate). Almost everything recorded
by the watch also goes to Strava, so most Strava activities are duplicates of
a Garmin one. A few (indoor rides sent straight to Strava) exist only there and
must stay.

Rules, for each Strava activity:

1. Strava kept the Garmin id in its ``external_id`` and we have that Garmin
   activity: **confirmed** duplicate.
2. Otherwise, Garmin activities that started less than 10 minutes apart and
   lasted about as long (less than 20 % difference):
   - exactly one: **confirmed** duplicate;
   - several: **possible** duplicate. We can't choose, so both stay visible and
     the user can hide one with a tap.
3. No match: a Strava-only activity, kept and counted normally.

Nothing is deleted: a confirmed duplicate simply points to its Garmin twin
(``duplicate_of_id``) and is left out of lists and counts. If the Garmin
library breaks, no Garmin twin appears for new sessions, so Strava ones are
counted again automatically: that is the fallback.
"""

import bisect
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, StrengthSession
from app.db.models.enums import DataSource

START_TOLERANCE = timedelta(minutes=10)
DURATION_TOLERANCE = 0.20  # 20 % of the longer of the two


class DuplicateStatus(StrEnum):
    CONFIRMED = "confirmed"
    POSSIBLE = "possible"


@dataclass
class DedupeResult:
    confirmed: int = 0
    possible: int = 0


def similar_duration(a: Activity, b: Activity) -> bool:
    longest = max(a.elapsed_time_s, b.elapsed_time_s, 1)
    return abs(a.elapsed_time_s - b.elapsed_time_s) <= DURATION_TOLERANCE * longest


class _GarminIndex:
    """Garmin activities sorted by start time, to find neighbours quickly (bisect)."""

    def __init__(self, activities: list[Activity]) -> None:
        self._sorted = sorted(activities, key=lambda a: a.start_time)
        self._starts = [a.start_time for a in self._sorted]
        self.by_garmin_id = {a.garmin_activity_id: a for a in activities if a.garmin_activity_id}

    def candidates(self, strava: Activity) -> list[Activity]:
        low = bisect.bisect_left(self._starts, strava.start_time - START_TOLERANCE)
        high = bisect.bisect_right(self._starts, strava.start_time + START_TOLERANCE)
        return [g for g in self._sorted[low:high] if similar_duration(g, strava)]


def find_twin(strava: Activity, index: _GarminIndex) -> tuple[Activity | None, str | None]:
    """The Garmin activity this Strava one duplicates, and how sure we are."""
    if strava.garmin_activity_id and strava.garmin_activity_id in index.by_garmin_id:
        return index.by_garmin_id[strava.garmin_activity_id], DuplicateStatus.CONFIRMED
    candidates = index.candidates(strava)
    if len(candidates) == 1:
        return candidates[0], DuplicateStatus.CONFIRMED
    if candidates:
        closest = min(candidates, key=lambda g: abs(g.start_time - strava.start_time))
        return closest, DuplicateStatus.POSSIBLE
    return None, None


def reconcile_duplicates(db: Session) -> DedupeResult:
    """Re-check every Strava activity against the Garmin ones, then commit.

    Cheap enough to run after every sync (a few thousand rows for one person),
    and running it again always gives the same result.
    """
    garmin = list(db.scalars(select(Activity).where(Activity.source == DataSource.GARMIN)))
    strava = list(db.scalars(select(Activity).where(Activity.source == DataSource.STRAVA)))
    index = _GarminIndex(garmin)
    result = DedupeResult()
    for activity in strava:
        twin, status = find_twin(activity, index)
        if twin is not None and status == DuplicateStatus.CONFIRMED:
            _carry_over(db, activity, twin)
            result.confirmed += 1
        elif status == DuplicateStatus.POSSIBLE:
            result.possible += 1
        activity.duplicate_of_id = twin.id if twin is not None else None
        activity.duplicate_status = status
    db.commit()
    return result


def _carry_over(db: Session, duplicate: Activity, kept: Activity) -> None:
    """What the user did on the Strava copy follows the kept Garmin activity.

    - a manual category correction (unless the Garmin one has its own);
    - the link of a typed strength session (unless the Garmin one has one).
    """
    if duplicate.category_override and not kept.category_override:
        kept.category_override = duplicate.category_override
    session = db.scalar(select(StrengthSession).where(StrengthSession.activity_id == duplicate.id))
    if session is None:
        return
    already_linked = db.scalar(
        select(StrengthSession.id).where(StrengthSession.activity_id == kept.id)
    )
    if already_linked is None:
        session.activity_id = kept.id
        db.flush()  # one session per activity: write before the next check
