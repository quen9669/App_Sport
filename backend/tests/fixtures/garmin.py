"""Fake Garmin Connect API for tests, shaped like ``garminconnect`` responses."""

from datetime import UTC, date, datetime, timedelta
from typing import Any


class GarminConnectTooManyRequestsError(Exception):
    """Same class name as the library's, which is how our provider recognises it."""


class GarminConnectConnectionError(Exception):
    pass


def sleep_payload(day: date, hours: float = 7.5, score: int = 82) -> dict[str, Any]:
    end = datetime(day.year, day.month, day.day, 5, 30, tzinfo=UTC)
    seconds = int(hours * 3600)
    return {
        "dailySleepDTO": {
            "calendarDate": day.isoformat(),
            "sleepTimeSeconds": seconds,
            "deepSleepSeconds": int(seconds * 0.18),
            "lightSleepSeconds": int(seconds * 0.58),
            "remSleepSeconds": int(seconds * 0.24),
            "awakeSleepSeconds": 1200,
            "sleepStartTimestampGMT": int(end.timestamp() * 1000) - seconds * 1000,
            "sleepEndTimestampGMT": int(end.timestamp() * 1000),
            "avgSleepHRV": 61.0,
            "sleepScores": {"overall": {"value": score, "qualifierKey": "GOOD"}},
        },
        "restingHeartRate": 49,
    }


# --- Activities -----------------------------------------------------------------


def garmin_activity(
    activity_id: int,
    start: datetime,
    type_key: str = "running",
    duration_s: float = 3600.0,
    distance_m: float = 10_000.0,
    average_hr: float | None = 142.0,
) -> dict[str, Any]:
    """One item of ``get_activities``, with the fields our mapper reads (and a few more)."""
    return {
        "activityId": activity_id,
        "activityName": f"Activité {activity_id}",
        # Garmin's format: UTC without offset; the local time is 2 h later in summer.
        "startTimeGMT": start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "startTimeLocal": (start.astimezone(UTC) + timedelta(hours=2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "activityType": {"typeId": 1, "typeKey": type_key},
        "duration": duration_s,
        "elapsedDuration": duration_s + 60,
        "movingDuration": duration_s - 30,
        "distance": distance_m,
        "elevationGain": 85.0,
        "averageSpeed": distance_m / duration_s if distance_m else 0.0,
        "maxSpeed": 4.1,
        "averageHR": average_hr,
        "maxHR": 171.0 if average_hr else None,
        "hasPolyline": distance_m > 0,
        "manualActivity": False,
    }


def activity_details(start: datetime, samples: int = 4, gps: bool = True) -> dict[str, Any]:
    """A small ``get_activity_details`` response: one sample every 5 seconds."""
    keys = ["directTimestamp", "directHeartRate", "directElevation", "sumDistance"]
    if gps:
        keys += ["directLatitude", "directLongitude"]
    start_ms = start.timestamp() * 1000
    rows = []
    for i in range(samples):
        metrics: list[float | None] = [start_ms + i * 5000, 120.0 + i, 300.0 + i, 12.5 * i]
        if gps:
            metrics += [49.61 + i * 0.0001, 6.13 + i * 0.0001]
        rows.append({"metrics": metrics})
    return {
        "activityId": 1,
        "metricDescriptors": [
            {"metricsIndex": index, "key": key, "unit": {}} for index, key in enumerate(keys)
        ],
        "activityDetailMetrics": rows,
    }


class FakeGarmin:
    """Implements the methods our Garmin code uses; can fail on demand.

    ``activities`` are items built with :func:`garmin_activity`, returned newest
    first and paged by offset, like the real ``get_activities``.
    """

    def __init__(self, activities: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[str] = []
        self.rate_limit_from: date | None = None
        self.broken = False
        self.no_sleep_days: set[str] = set()
        self.activities = sorted(
            activities or [], key=lambda a: str(a["startTimeGMT"]), reverse=True
        )
        self.detail_calls: list[str] = []
        self.rate_limit_details = False
        self.weight_range: tuple[str, str | None] | None = None
        self.weigh_ins: list[dict[str, Any]] = []

    def _check(self, cdate: str) -> None:
        self.calls.append(cdate)
        if self.broken:
            raise GarminConnectConnectionError("Garmin changed something")
        if self.rate_limit_from and date.fromisoformat(cdate) >= self.rate_limit_from:
            raise GarminConnectTooManyRequestsError()

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        self._check(cdate)
        if cdate in self.no_sleep_days:
            return {"dailySleepDTO": {"sleepTimeSeconds": None}}
        return sleep_payload(date.fromisoformat(cdate))

    def get_stats(self, cdate: str) -> dict[str, Any]:
        return {
            "calendarDate": cdate,
            "restingHeartRate": 49,
            "totalSteps": 10423,
            "averageStressLevel": 28,
            "bodyBatteryHighestValue": 92,
            "bodyBatteryLowestValue": 14,
            "moderateIntensityMinutes": 22,
            "vigorousIntensityMinutes": 15,
        }

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        return {"hrvSummary": {"calendarDate": cdate, "lastNightAvg": 61.0, "weeklyAvg": 59.0}}

    def get_max_metrics(self, cdate: str) -> list[dict[str, Any]]:
        return [{"generic": {"calendarDate": cdate, "vo2MaxPreciseValue": 52.4, "vo2MaxValue": 52}}]

    def get_body_composition(self, startdate: str, enddate: str | None = None) -> dict[str, Any]:
        """Two weigh-ins on the same day (the later one counts) and an older one."""
        self.weight_range = (startdate, enddate)
        return {"dateWeightList": self.weigh_ins}

    def get_activities(self, start: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        if self.broken:
            raise GarminConnectConnectionError("Garmin changed something")
        return self.activities[start : start + limit]

    def get_activity_details(
        self, activity_id: str, maxchart: int = 2000, maxpoly: int = 4000
    ) -> dict[str, Any]:
        self.detail_calls.append(activity_id)
        if self.rate_limit_details:
            raise GarminConnectTooManyRequestsError()
        item = next(a for a in self.activities if str(a["activityId"]) == activity_id)
        start = datetime.strptime(str(item["startTimeGMT"]), "%Y-%m-%d %H:%M:%S")
        return activity_details(start.replace(tzinfo=UTC), gps=bool(item["distance"]))
