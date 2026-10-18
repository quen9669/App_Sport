"""Which goal an activity counts for: strength, cardio, transport or other.

All the rules live in this one file so they are easy to read and to change.
The automatic category comes from the sport type of the source (Strava
``sport_type`` or Garmin ``typeKey``, stored as is in ``Activity.sport_type``);
a manual correction (``Activity.category_override``) always wins over it.

"Transport" ("Déplacement" in the interface) is FRANKS's rule: a walk, or a
short outdoor ride (under 5 km), is a way of getting somewhere, not a workout.
It counts in no session or minute goal, but still in the training load.
"""

from enum import StrEnum

from app.db.models import Activity


class Category(StrEnum):
    STRENGTH = "strength"  # "musculation" in the interface
    CARDIO = "cardio"
    TRANSPORT = "transport"  # "déplacement": walks and short rides, not sport
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
# Walking is a way of getting around (FRANKS's decision), whatever its length.
# Hikes stay OTHER: they are an outing, not a trip to work.
_WALKING = ("Walk", "walking", "casual_walking", "speed_walking")
CATEGORY_BY_SPORT.update(dict.fromkeys(_WALKING, Category.TRANSPORT))
# Everything else (Yoga, Pilates, Hike, Garmin "hiking", "yoga"...) is OTHER.

# Sport groups used by distance goals ("km of running per week").
RUN_SPORTS = frozenset({"Run", "TrailRun", "VirtualRun", *_GARMIN_RUN})
RIDE_SPORTS = frozenset(
    {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide", *_GARMIN_RIDE}
)


# A ride shorter than this is a trip (to work, to the shops), not a workout.
TRANSPORT_RIDE_MAX_M = 5000.0
# Indoor rides never take you anywhere, and often report no real distance.
_INDOOR_RIDES = frozenset({"VirtualRide", "indoor_cycling", "virtual_ride"})


def automatic_category(sport_type: str, distance_m: float | None = None) -> Category:
    """The rule: the sport type, plus the distance for rides (short ride = transport).

    Without a known distance a ride stays cardio: better count a real workout
    than hide it.
    """
    if (
        sport_type in RIDE_SPORTS
        and sport_type not in _INDOOR_RIDES
        and distance_m is not None
        and distance_m < TRANSPORT_RIDE_MAX_M
    ):
        return Category.TRANSPORT
    return CATEGORY_BY_SPORT.get(sport_type, Category.OTHER)


def activity_automatic_category(activity: Activity) -> Category:
    """`automatic_category` for a stored activity (its sport type and distance)."""
    return automatic_category(activity.sport_type, activity.distance_m)


def effective_category(activity: Activity) -> Category:
    """The category used everywhere: the manual correction if any, else the rule."""
    if activity.category_override:
        try:
            return Category(activity.category_override)
        except ValueError:
            pass  # an unknown value in the database: fall back to the rule
    return activity_automatic_category(activity)
