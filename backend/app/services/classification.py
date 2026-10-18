"""Which goal an activity counts for: strength, cardio or other.

All the rules live in this one file so they are easy to read and to change.
The automatic category comes from the Strava sport type; a manual correction
(``Activity.category_override``) always wins over it.
"""

from enum import StrEnum

from app.db.models import Activity


class Category(StrEnum):
    STRENGTH = "strength"  # "musculation" in the interface
    CARDIO = "cardio"
    OTHER = "other"  # shown, but not counted in session goals


# Strava sport types (https://developers.strava.com/docs/reference/#api-models-SportType).
# Group gym classes (Body Pump, cross training) are usually recorded as "Workout",
# "Crossfit" or "HighIntensityIntervalTraining": FRANKS decided they count as strength.
CATEGORY_BY_SPORT: dict[str, Category] = {
    "WeightTraining": Category.STRENGTH,
    "Crossfit": Category.STRENGTH,
    "Workout": Category.STRENGTH,
    "HighIntensityIntervalTraining": Category.STRENGTH,
    "Run": Category.CARDIO,
    "TrailRun": Category.CARDIO,
    "VirtualRun": Category.CARDIO,
    "Ride": Category.CARDIO,
    "VirtualRide": Category.CARDIO,
    "GravelRide": Category.CARDIO,
    "MountainBikeRide": Category.CARDIO,
    "EBikeRide": Category.CARDIO,
    "Swim": Category.CARDIO,
    "Rowing": Category.CARDIO,
    "VirtualRow": Category.CARDIO,
    "Elliptical": Category.CARDIO,
    "StairStepper": Category.CARDIO,
}
# Everything else (Yoga, Pilates, Walk, Hike...) falls back to OTHER.

# Sport groups used by distance goals ("km of running per week").
RUN_SPORTS = frozenset({"Run", "TrailRun", "VirtualRun"})
RIDE_SPORTS = frozenset({"Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide"})


def automatic_category(sport_type: str) -> Category:
    return CATEGORY_BY_SPORT.get(sport_type, Category.OTHER)


def effective_category(activity: Activity) -> Category:
    """The category used everywhere: the manual correction if any, else the rule."""
    if activity.category_override:
        try:
            return Category(activity.category_override)
        except ValueError:
            pass  # an unknown value in the database: fall back to the rule
    return automatic_category(activity.sport_type)
