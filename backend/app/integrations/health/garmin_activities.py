"""Convert Garmin Connect activity payloads into the values of our own tables.

⚠️ The field names below come from the unofficial ``garminconnect`` library
(``get_activities`` and ``get_activity_details``), which returns the JSON of the
Garmin Connect website as is. They are not documented by Garmin: they must be
checked on real data, and Pydantic validation turns a format change into a
clear error instead of corrupted data.

Everything is converted to the same shape as Strava activities (SI units,
UTC start time, streams named like Strava's), so the rest of the app does not
care where an activity comes from.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.services import polyline

# Garmin types recorded indoors (no GPS): shown as "home trainer / treadmill".
INDOOR_TYPES = frozenset(
    {"indoor_cycling", "treadmill_running", "indoor_running", "virtual_ride", "virtual_run"}
)
# The map only needs a light route; the detailed one stays in the streams.
MAX_SUMMARY_POINTS = 500


class GarminActivityType(BaseModel):
    model_config = ConfigDict(extra="ignore", alias_generator=to_camel)
    type_key: str = "other"  # e.g. "running", "indoor_cycling", "strength_training"


class GarminActivitySummary(BaseModel):
    """One item of ``get_activities``. Unknown fields are ignored.

    ``alias_generator=to_camel`` reads Garmin's camelCase JSON into snake_case
    attributes (``activityId`` -> ``activity_id``); the few names that don't
    follow the pattern ("GMT", "HR") get an explicit alias.
    """

    model_config = ConfigDict(extra="ignore", alias_generator=to_camel)

    activity_id: int
    activity_name: str | None = None
    # "2026-10-12 06:30:00", in UTC ("GMT"). We never use startTimeLocal: it has
    # no timezone and would shift every activity by one or two hours.
    start_time_gmt: datetime = Field(alias="startTimeGMT")
    activity_type: GarminActivityType = Field(default_factory=GarminActivityType)
    duration: float | None = None  # seconds
    elapsed_duration: float | None = None
    moving_duration: float | None = None
    distance: float | None = None  # metres
    elevation_gain: float | None = None
    average_speed: float | None = None  # m/s
    max_speed: float | None = None
    average_hr: float | None = Field(default=None, alias="averageHR")
    max_hr: float | None = Field(default=None, alias="maxHR")
    average_running_cadence_in_steps_per_minute: float | None = None
    average_biking_cadence_in_rev_per_minute: float | None = None
    manual_activity: bool = False

    @field_validator("start_time_gmt", mode="after")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # The string has no offset: say explicitly that it is UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _positive(value: float | None) -> float | None:
    """Garmin sends 0.0 for "no data" (e.g. distance of a gym session)."""
    return value if value else None


def activity_fields(summary: GarminActivitySummary) -> dict[str, Any]:
    """Column values for an :class:`~app.db.models.Activity` row (without source/id)."""
    type_key = summary.activity_type.type_key
    elapsed = summary.elapsed_duration or summary.duration or 0
    moving = summary.moving_duration or summary.duration
    cadence = (
        summary.average_running_cadence_in_steps_per_minute
        or summary.average_biking_cadence_in_rev_per_minute
    )
    return {
        "name": summary.activity_name or type_key,
        "sport_type": type_key,
        "start_time": summary.start_time_gmt,
        "timezone": None,  # Garmin gives a numeric zone id only; the app timezone is used
        "elapsed_time_s": round(elapsed),
        "moving_time_s": round(moving) if moving else None,
        "distance_m": _positive(summary.distance),
        "elevation_gain_m": _positive(summary.elevation_gain),
        "average_speed_mps": _positive(summary.average_speed),
        "max_speed_mps": _positive(summary.max_speed),
        "average_heartrate": _positive(summary.average_hr),
        "max_heartrate": _positive(summary.max_hr),
        "average_cadence": _positive(cadence),
        "has_heartrate": bool(summary.average_hr),
        "is_manual": summary.manual_activity,
        "is_trainer": type_key in INDOOR_TYPES,
        # Garmin rows carry their own id here, which is what Strava rows are compared to.
        "garmin_activity_id": str(summary.activity_id),
    }


# Garmin metric keys -> our stream names (the same names as Strava streams).
_METRIC_TO_STREAM = {
    "directHeartRate": "heartrate",
    "directElevation": "altitude",
    "directSpeed": "velocity_smooth",
    "sumDistance": "distance",
}


def _metric_indexes(details: dict[str, Any]) -> dict[str, int]:
    """``metricDescriptors`` say which position of each sample holds which metric."""
    indexes = {}
    for descriptor in details.get("metricDescriptors") or []:
        if isinstance(descriptor, dict) and isinstance(descriptor.get("metricsIndex"), int):
            indexes[str(descriptor.get("key"))] = descriptor["metricsIndex"]
    return indexes


def _value(metrics: list[Any], index: int | None) -> Any:
    if index is None or index >= len(metrics):
        return None
    value = metrics[index]
    return value if isinstance(value, int | float) and not isinstance(value, bool) else None


def details_to_series(details: dict[str, Any]) -> dict[str, list[Any]]:
    """Turn ``get_activity_details`` into aligned series (one value per sample).

    Input (simplified)::

        {"metricDescriptors": [{"metricsIndex": 0, "key": "directTimestamp"}, ...],
         "activityDetailMetrics": [{"metrics": [1760250600000.0, 121.0, ...]}, ...]}

    Output: ``{"time": [0, 5, ...], "heartrate": [121, ...], "latlng": [[49.6, 6.1], ...]}``.
    A series with no value at all is left out; missing samples stay ``None`` so
    that every series keeps the same length as ``time``.
    """
    indexes = _metric_indexes(details)
    samples = [
        row["metrics"]
        for row in details.get("activityDetailMetrics") or []
        if isinstance(row, dict) and isinstance(row.get("metrics"), list)
    ]
    timestamps = [_value(sample, indexes.get("directTimestamp")) for sample in samples]
    if not samples or timestamps[0] is None:
        return {}
    first = timestamps[0]
    series: dict[str, list[Any]] = {
        # Seconds since the start, like Strava's "time" stream.
        "time": [round((ts - first) / 1000) if ts is not None else None for ts in timestamps]
    }
    for key, name in _METRIC_TO_STREAM.items():
        values = [_value(sample, indexes.get(key)) for sample in samples]
        if any(value is not None for value in values):
            series[name] = values
    lat_index, lng_index = indexes.get("directLatitude"), indexes.get("directLongitude")
    latlng = [_latlng(_value(s, lat_index), _value(s, lng_index)) for s in samples]
    if any(point is not None for point in latlng):
        series["latlng"] = latlng
    return series


def _latlng(lat: Any, lng: Any) -> list[float] | None:
    return [lat, lng] if lat is not None and lng is not None else None


def summary_polyline(series: dict[str, list[Any]]) -> str | None:
    """A light encoded route for the map, from the detailed GPS samples.

    Keeps one point every few so the route has at most MAX_SUMMARY_POINTS
    points. (Phase 3b adds a smarter simplification for the map.)
    """
    points = [(p[0], p[1]) for p in series.get("latlng", []) if p is not None]
    if len(points) < 2:
        return None
    step = max(1, -(-len(points) // MAX_SUMMARY_POINTS))  # ceiling division
    kept = points[::step]
    if kept[-1] != points[-1]:
        kept.append(points[-1])  # always end where the activity ended
    return polyline.encode(kept)
