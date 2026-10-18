"""Fake Garmin Connect API for tests, shaped like ``garminconnect`` responses."""

from datetime import UTC, date, datetime
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


class FakeGarmin:
    """Implements the 4 methods the provider uses; can fail on demand."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.rate_limit_from: date | None = None
        self.broken = False
        self.no_sleep_days: set[str] = set()

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
        }

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        return {"hrvSummary": {"calendarDate": cdate, "lastNightAvg": 61.0, "weeklyAvg": 59.0}}

    def get_max_metrics(self, cdate: str) -> list[dict[str, Any]]:
        return [{"generic": {"calendarDate": cdate, "vo2MaxPreciseValue": 52.4, "vo2MaxValue": 52}}]
