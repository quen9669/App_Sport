"""Realistic fake Strava data and a fake Strava API for tests.

The JSON shapes follow the official API reference
(https://developers.strava.com/docs/reference/): SummaryActivity, StreamSet, Token.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx

from app.integrations.strava.client import API_BASE_URL
from app.integrations.strava.oauth import TOKEN_URL

BASE_TIME = datetime(2026, 1, 5, 6, 30, tzinfo=UTC)

# Polyline of a short loop in Luxembourg City (Google encoded polyline format).
SAMPLE_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def make_activity(
    activity_id: int,
    start: datetime,
    sport_type: str = "Run",
    *,
    distance: float = 10_000.0,
    moving_time: int = 3_000,
    with_gps: bool = True,
    with_heartrate: bool = True,
) -> dict[str, Any]:
    """One Strava SummaryActivity, as returned by GET /athlete/activities."""
    return {
        "resource_state": 2,
        "athlete": {"id": 987654, "resource_state": 1},
        "id": activity_id,
        "name": f"{sport_type} #{activity_id}",
        "distance": distance,
        "moving_time": moving_time,
        "elapsed_time": moving_time + 120,
        "total_elevation_gain": 85.0,
        "type": sport_type,
        "sport_type": sport_type,
        "start_date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_date_local": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "(GMT+01:00) Europe/Luxembourg",
        "map": {"id": f"a{activity_id}", "summary_polyline": SAMPLE_POLYLINE if with_gps else ""},
        "trainer": False,
        "manual": False,
        "average_speed": distance / moving_time if moving_time else 0.0,
        "max_speed": 4.8,
        "has_heartrate": with_heartrate,
        "average_heartrate": 148.2 if with_heartrate else None,
        "max_heartrate": 172.0 if with_heartrate else None,
        "average_cadence": 84.5,
    }


def make_history(count: int, days_apart: int = 2) -> list[dict[str, Any]]:
    """``count`` activities, oldest first, alternating run / ride / gym class."""
    sports = ["Run", "Ride", "WeightTraining", "Workout"]
    activities = []
    for index in range(count):
        sport = sports[index % len(sports)]
        indoor = sport in ("WeightTraining", "Workout")
        activities.append(
            make_activity(
                1000 + index,
                BASE_TIME + timedelta(days=index * days_apart),
                sport,
                distance=0.0 if indoor else 10_000.0,
                with_gps=not indoor,
            )
        )
    return activities


def make_streams(points: int = 60) -> dict[str, Any]:
    """A key_by_type StreamSet, as returned by GET /activities/{id}/streams."""

    def series(data: list[Any]) -> dict[str, Any]:
        return {"data": data, "series_type": "time", "original_size": points, "resolution": "high"}

    return {
        "time": series(list(range(points))),
        "latlng": series([[49.6116 + i * 1e-4, 6.1319 + i * 1e-4] for i in range(points)]),
        "heartrate": series([130 + i % 20 for i in range(points)]),
        "altitude": series([300.0 + (i % 10) for i in range(points)]),
    }


def rate_limit_headers(short_usage: int = 1, daily_usage: int = 1) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": "200,2000",
        "X-RateLimit-Usage": f"{short_usage},{daily_usage}",
        "X-ReadRateLimit-Limit": "100,1000",
        "X-ReadRateLimit-Usage": f"{short_usage},{daily_usage}",
    }


def token_response(
    access: str = "access-1", refresh: str = "refresh-1", expires_in: int = 21_600
) -> dict[str, Any]:
    expires_at = int(datetime.now(UTC).timestamp()) + expires_in
    return {
        "token_type": "Bearer",
        "expires_at": expires_at,
        "expires_in": expires_in,
        "refresh_token": refresh,
        "access_token": access,
        "athlete": {"id": 987654, "username": "franks"},
    }


class FakeStravaApi:
    """In-memory imitation of the Strava endpoints the sync uses.

    It honours ``before``, ``after``, ``page`` and ``per_page`` like the real
    API (newest first), counts calls, and can simulate an exhausted daily quota.
    """

    def __init__(self, activities: list[dict[str, Any]]) -> None:
        self.activities = activities
        self.streams_without_data: set[str] = set()
        self.daily_usage = 0
        self.daily_limit = 1000
        self.calls: list[str] = []

    def install(self, router: respx.MockRouter) -> None:
        router.get(f"{API_BASE_URL}/athlete/activities").mock(side_effect=self._list)
        router.get(url__regex=rf"{re.escape(API_BASE_URL)}/activities/(?P<aid>\d+)/streams").mock(
            side_effect=self._streams
        )
        router.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token_response()))

    def _headers(self) -> dict[str, str]:
        self.daily_usage += 1
        return {
            "X-ReadRateLimit-Limit": f"100,{self.daily_limit}",
            "X-ReadRateLimit-Usage": f"1,{self.daily_usage}",
        }

    def _list(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("list")
        params = request.url.params
        items = sorted(self.activities, key=lambda a: a["start_date"], reverse=True)

        def epoch(activity: dict[str, Any]) -> int:
            return int(
                datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
                .replace(tzinfo=UTC)
                .timestamp()
            )

        if "before" in params:
            items = [a for a in items if epoch(a) < int(params["before"])]
        if "after" in params:
            items = [a for a in items if epoch(a) > int(params["after"])]
        page, per_page = int(params.get("page", 1)), int(params.get("per_page", 30))
        page_items = items[(page - 1) * per_page : page * per_page]
        return httpx.Response(200, json=page_items, headers=self._headers())

    def _streams(self, request: httpx.Request, aid: str) -> httpx.Response:
        self.calls.append(f"streams:{aid}")
        if aid in self.streams_without_data:
            return httpx.Response(
                404, json={"message": "Record Not Found"}, headers=self._headers()
            )
        return httpx.Response(200, json=make_streams(), headers=self._headers())
