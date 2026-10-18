"""Which goal an activity counts for: strength, cardio or other.

All the rules live in this one file so they are easy to read and to change.
The automatic category comes from the sport type of the source (Strava
``sport_type`` or Garmin ``typeKey``, stored as is in ``Activity.sport_type``);
a manual correction (``Activity.category_override``) always wins over it.
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

# Garmin Connect activity types ("typeKey"), since Garmin is the main source.
# Same rules as above: gym classes recorded on the watch as "Cardio"
# (indoor_cardio), "HIIT" or "Fitness Equipment" count as strength, like their
# Strava equivalent "Workout". A wrong guess is fixed by hand in the app.
_GARMIN_STRENGTH = ("strength_training", "hiit", "indoor_cardio", "fitness_equipment")
_GARMIN_RUN = (
    "running",
    "trail_running",
    "treadmill_running",
    "indoor_running",
    "track_running",
    "street_running",
    "virtual_run",
)
_GARMIN_RIDE = (
    "cycling",
    "road_biking",
    "indoor_cycling",
    "mountain_biking",
    "gravel_cycling",
    "cyclocross",
    "virtual_ride",
    "e_bike_fitness",
    "e_bike_mountain",
)
_GARMIN_OTHER_CARDIO = (
    "lap_swimming",
    "open_water_swimming",
    "swimming",
    "indoor_rowing",
    "rowing",
    "elliptical",
    "stair_climbing",
)
CATEGORY_BY_SPORT.update(dict.fromkeys(_GARMIN_STRENGTH, Category.STRENGTH))
CATEGORY_BY_SPORT.update(
    dict.fromkeys(_GARMIN_RUN + _GARMIN_RIDE + _GARMIN_OTHER_CARDIO, Category.CARDIO)
)
# Everything else (Yoga, Pilates, Walk, Hike, Garmin "walking", "yoga"...) is OTHER.

# Sport groups used by distance goals ("km of running per week").
RUN_SPORTS = frozenset({"Run", "TrailRun", "VirtualRun", *_GARMIN_RUN})
RIDE_SPORTS = frozenset(
    {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide", *_GARMIN_RIDE}
)


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
