"""HTTP client for the Strava API, with quotas, retries and token handling."""

import time
from collections.abc import Callable
from typing import Any

import httpx

from app.integrations.strava.rate_limit import RateLimiter

API_BASE_URL = "https://www.strava.com/api/v3"

# Series we ask for. "key_by_type" makes Strava return {"heartrate": {...}, ...}.
STREAM_KEYS = (
    "time",
    "latlng",
    "distance",
    "altitude",
    "velocity_smooth",
    "heartrate",
    "cadence",
    "watts",
    "grade_smooth",
    "moving",
)

MAX_PER_PAGE = 200  # maximum allowed by Strava
_MAX_RETRIES = 3


class StravaApiError(RuntimeError):
    """Strava answered with an unexpected error."""

    def __init__(self, status_code: int, path: str) -> None:
        super().__init__(f"Strava API error HTTP {status_code} on {path}")
        self.status_code = status_code


class StravaClient:
    """Read-only access to the Strava endpoints we need.

    ``access_token`` is a function, not a string: it is called before each
    request so that a token refreshed in the meantime is always used.
    """

    def __init__(
        self,
        http: httpx.Client,
        access_token: Callable[[], str],
        rate_limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http
        self._access_token = access_token
        self._rate_limiter = rate_limiter or RateLimiter(sleep=sleep)
        self._sleep = sleep

    def list_activities(
        self,
        *,
        after: int | None = None,
        before: int | None = None,
        page: int = 1,
        per_page: int = MAX_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """One page of activity summaries. ``after``/``before`` are Unix timestamps."""
        params: dict[str, int] = {"page": page, "per_page": per_page}
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        result: list[dict[str, Any]] = self._get("/athlete/activities", params)
        return result

    def get_activity_streams(self, activity_id: str) -> dict[str, Any]:
        """All available time series of one activity, keyed by type.

        Returns ``{}`` when the activity has no streams (e.g. a manual entry).
        """
        params = {"keys": ",".join(STREAM_KEYS), "key_by_type": "true"}
        try:
            result: dict[str, Any] = self._get(f"/activities/{activity_id}/streams", params)
        except StravaApiError as exc:
            if exc.status_code == 404:
                return {}
            raise
        return result

    def get_athlete_zones(self) -> dict[str, Any]:
        """Heart-rate (and power) zones configured on Strava."""
        result: dict[str, Any] = self._get("/athlete/zones", {})
        return result

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        """GET with quota handling and retries.

        - 429 (too many requests): wait for the next 15-minute window, retry.
        - 5xx or network error: wait 1 s, 2 s, 4 s (exponential backoff), retry.
        - other errors: raise immediately, retrying would not help.
        """
        for attempt in range(_MAX_RETRIES + 1):
            self._rate_limiter.before_request()
            try:
                response = self._http.get(
                    f"{API_BASE_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx.TransportError:
                if attempt == _MAX_RETRIES:
                    raise
                self._sleep(2**attempt)
                continue

            self._rate_limiter.update_from_headers(response.headers)
            if response.status_code == 200:
                return response.json()
            if attempt < _MAX_RETRIES:
                if response.status_code == 429:
                    self._rate_limiter.wait_for_next_window()
                    continue
                if response.status_code >= 500:
                    self._sleep(2**attempt)
                    continue
            raise StravaApiError(response.status_code, path)
        raise AssertionError("unreachable")  # the loop always returns or raises
