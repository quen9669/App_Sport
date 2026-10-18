"""Convert Strava JSON payloads into the values of our own tables.

Pydantic validates the payload first: if Strava changes a field type, we get a
clear validation error here instead of corrupted data in the database.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StravaMap(BaseModel):
    summary_polyline: str | None = None


class StravaActivitySummary(BaseModel):
    """Fields of a Strava "SummaryActivity" that we keep. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""
    sport_type: str | None = None
    type: str | None = None  # older field, used when sport_type is missing
    start_date: datetime  # UTC, e.g. "2026-10-12T06:30:00Z"
    timezone: str | None = None  # e.g. "(GMT+01:00) Europe/Luxembourg"
    elapsed_time: int
    moving_time: int | None = None
    distance: float | None = None
    total_elevation_gain: float | None = None
    average_speed: float | None = None
    max_speed: float | None = None
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    average_cadence: float | None = None
    map: StravaMap = Field(default_factory=StravaMap)
    has_heartrate: bool = False
    manual: bool = False
    trainer: bool = False


def parse_timezone(value: str | None) -> str | None:
    """Extract the IANA name from Strava's "(GMT+01:00) Europe/Luxembourg" format."""
    if not value:
        return None
    return value.rsplit(" ", 1)[-1] or None


def activity_fields(summary: StravaActivitySummary) -> dict[str, Any]:
    """Column values for an :class:`~app.db.models.Activity` row (without source/id)."""
    return {
        "name": summary.name,
        "sport_type": summary.sport_type or summary.type or "Unknown",
        "start_time": summary.start_date,
        "timezone": parse_timezone(summary.timezone),
        "elapsed_time_s": summary.elapsed_time,
        "moving_time_s": summary.moving_time,
        "distance_m": summary.distance,
        "elevation_gain_m": summary.total_elevation_gain,
        "average_speed_mps": summary.average_speed,
        "max_speed_mps": summary.max_speed,
        "average_heartrate": summary.average_heartrate,
        "max_heartrate": summary.max_heartrate,
        "average_cadence": summary.average_cadence,
        "summary_polyline": summary.map.summary_polyline or None,
        "has_heartrate": summary.has_heartrate,
        "is_manual": summary.manual,
        "is_trainer": summary.trainer,
    }


def streams_to_series(payload: dict[str, Any]) -> dict[str, list[Any]]:
    """Keep only the data arrays of a key_by_type streams response.

    Input:  {"heartrate": {"data": [120, 121], "series_type": "time", ...}, ...}
    Output: {"heartrate": [120, 121], ...}
    """
    return {
        key: value["data"]
        for key, value in payload.items()
        if isinstance(value, dict) and isinstance(value.get("data"), list)
    }
