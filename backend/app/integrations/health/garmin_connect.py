"""Garmin Connect through the unofficial ``garminconnect`` library.

⚠️ Unofficial: this library imitates the Garmin Connect website. Garmin can
change its login or endpoints at any time and break it. Everything here is
built so that a breakage only produces a "failed" sync entry; the rest of the
app keeps working, and file import (``file_import.py``) remains available.

Session tokens are saved in ``GARMIN_TOKENSTORE`` (outside the repository), so
we log in with the password only once and then reuse the tokens, which also
avoids Garmin's limits on repeated logins.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.db.models.enums import DataSource
from app.integrations.health.provider import (
    DailyHealthRecord,
    HealthBatch,
    HealthProviderError,
    HealthRateLimitedError,
    SleepRecord,
    WeightRecord,
)
from app.integrations.health.validation import check_daily, check_sleep, plausible_weight

logger = logging.getLogger(__name__)

WEIGHT_LOOKBACK = timedelta(days=365)


class GarminApi(Protocol):
    """The few methods of ``garminconnect.Garmin`` we use (lets tests pass a fake)."""

    def get_sleep_data(self, cdate: str) -> dict[str, Any]: ...
    def get_stats(self, cdate: str) -> dict[str, Any]: ...
    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None: ...
    def get_max_metrics(self, cdate: str) -> Any: ...
    # Weigh-ins between two dates ("YYYY-MM-DD"), weights in grams.
    def get_body_composition(self, startdate: str, enddate: str | None = None) -> Any: ...
    # Activities, newest first: ``start`` is an offset (0 = most recent).
    def get_activities(self, start: int = 0, limit: int = 20) -> Any: ...
    # Detailed samples (heart rate, GPS, altitude, speed) of one activity.
    def get_activity_details(
        self, activity_id: str, maxchart: int = 2000, maxpoly: int = 4000
    ) -> Any: ...


def login_with_library(email: str, password: str, tokenstore: str) -> GarminApi:
    """Log in with the real library, reusing saved tokens when possible.

    The import is done here, not at the top of the file: if the library is
    missing or broken, only Garmin syncs fail, the app still starts.
    """
    try:
        from garminconnect import Garmin, GarminConnectAuthenticationError
    except Exception as exc:  # broken install, incompatible version...
        raise HealthProviderError(
            f"garminconnect library unavailable: {type(exc).__name__}"
        ) from None

    store = Path(tokenstore).expanduser()
    store.mkdir(parents=True, exist_ok=True, mode=0o700)  # readable by you only
    client = Garmin(email=email or None, password=password or None)
    try:
        client.login(str(store))
    except GarminConnectAuthenticationError:
        raise HealthProviderError(
            "Garmin login refused: check GARMIN_EMAIL / GARMIN_PASSWORD in .env"
        ) from None
    except Exception as exc:
        raise HealthProviderError(f"Garmin login failed: {type(exc).__name__}") from None
    return client


def _ms_to_datetime(value: Any) -> datetime | None:
    """Garmin timestamps are milliseconds since 1970 (UTC for the *GMT fields)."""
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _int(value: Any) -> int | None:
    number = _number(value)
    return int(round(number)) if number is not None else None


def map_sleep(day: date, payload: dict[str, Any]) -> SleepRecord | None:
    """Convert a ``get_sleep_data`` response; None when the night has no sleep recorded."""
    dto = payload.get("dailySleepDTO") or {}
    duration = _int(dto.get("sleepTimeSeconds"))
    if not duration:
        return None
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    return SleepRecord(
        night_date=day,
        sleep_start=_ms_to_datetime(dto.get("sleepStartTimestampGMT")),
        sleep_end=_ms_to_datetime(dto.get("sleepEndTimestampGMT")),
        duration_s=duration,
        score=_int(overall.get("value")),
        deep_s=_int(dto.get("deepSleepSeconds")),
        light_s=_int(dto.get("lightSleepSeconds")),
        rem_s=_int(dto.get("remSleepSeconds")),
        awake_s=_int(dto.get("awakeSleepSeconds")),
        resting_heartrate=_int(payload.get("restingHeartRate")),
        hrv_ms=_number(dto.get("avgSleepHRV")) or _number(payload.get("avgOvernightHrv")),
        raw=payload,
    )


def _vo2max(max_metrics: Any) -> float | None:
    """``get_max_metrics`` returns a list of entries holding a "generic" block."""
    entries = max_metrics if isinstance(max_metrics, list) else [max_metrics]
    for entry in entries:
        if isinstance(entry, dict):
            generic = entry.get("generic") or {}
            value = _number(generic.get("vo2MaxPreciseValue")) or _number(
                generic.get("vo2MaxValue")
            )
            if value is not None:
                return value
    return None


def map_daily(
    day: date, stats: dict[str, Any], hrv: dict[str, Any] | None, max_metrics: Any
) -> DailyHealthRecord:
    hrv_summary = (hrv or {}).get("hrvSummary") or {}
    return DailyHealthRecord(
        day=day,
        resting_heartrate=_int(stats.get("restingHeartRate")),
        hrv_ms=_number(hrv_summary.get("lastNightAvg")),
        stress_avg=_int(stats.get("averageStressLevel")),
        steps=_int(stats.get("totalSteps")),
        vo2max=_vo2max(max_metrics),
        body_battery_max=_int(stats.get("bodyBatteryHighestValue")),
        body_battery_min=_int(stats.get("bodyBatteryLowestValue")),
        raw={"stats": stats, "hrv": hrv, "max_metrics": max_metrics},
    )


def map_weights(payload: Any) -> list[WeightRecord]:
    """Convert ``get_body_composition``: one weigh-in per day, the last one of the day.

    ⚠️ Shape from the library, to check on real data:
    ``{"dateWeightList": [{"calendarDate": "2026-10-12", "date": 1760252400000,
    "weight": 79600.0, "bodyFat": 18.2}, ...]}``, weights in **grams**.
    """
    entries = payload.get("dateWeightList") if isinstance(payload, dict) else None
    by_day: dict[date, WeightRecord] = {}
    for entry in sorted(entries or [], key=lambda e: _number(e.get("date")) or 0):
        grams = _number(entry.get("weight")) if isinstance(entry, dict) else None
        day_text = entry.get("calendarDate") if isinstance(entry, dict) else None
        if grams is None or not isinstance(day_text, str):
            continue
        day = date.fromisoformat(day_text)
        # Sorted by time: a later weigh-in of the same day replaces the earlier one.
        by_day[day] = WeightRecord(
            day=day,
            weight_kg=round(grams / 1000, 1),
            body_fat_pct=_number(entry.get("bodyFat")),
            raw=entry,
        )
    return [record for record in by_day.values() if plausible_weight(record)]


class GarminConnectProvider:
    """Health data from Garmin Connect, one day at a time."""

    source: str = DataSource.GARMIN

    def __init__(self, login: Callable[[], GarminApi]) -> None:
        # ``login`` is called on first use only, so building the provider is free.
        self._login = login
        self._api: GarminApi | None = None

    def fetch_range(self, start: date, end: date) -> HealthBatch:
        batch = HealthBatch()
        day = start
        while day <= end:
            try:
                self._fetch_day(day, batch)
            except HealthRateLimitedError:
                # Keep what we have; the sync stores it and resumes next run.
                batch.warnings.append(f"Garmin rate limit reached at {day}, stopping here")
                return batch
            day += timedelta(days=1)
        # Weigh-ins are rare (sometimes one a month): always look a year back, so
        # the last one is known even when the sync only re-reads the last days.
        self._fetch_weights(min(start, end - WEIGHT_LOOKBACK), end, batch)
        return batch

    def _fetch_weights(self, start: date, end: date, batch: HealthBatch) -> None:
        """All weigh-ins of the range in one request (unlike sleep, fetched day by day)."""
        api = self._api_client()
        try:
            payload = call_garmin(api.get_body_composition, start.isoformat(), end.isoformat())
        except HealthRateLimitedError:
            batch.warnings.append("Garmin rate limit reached before weigh-ins, next run")
            return
        batch.weights.extend(map_weights(payload))

    def _api_client(self) -> GarminApi:
        if self._api is None:
            self._api = self._login()
        return self._api

    def _fetch_day(self, day: date, batch: HealthBatch) -> None:
        api = self._api_client()
        cdate = day.isoformat()
        sleep_payload = self._call(api.get_sleep_data, cdate)
        stats = self._call(api.get_stats, cdate) or {}
        hrv = self._call(api.get_hrv_data, cdate)
        max_metrics = self._call(api.get_max_metrics, cdate)

        if isinstance(sleep_payload, dict):
            sleep = map_sleep(day, sleep_payload)
            if sleep is not None:
                batch.warnings.extend(check_sleep(sleep))
                batch.sleep.append(sleep)
        daily = map_daily(day, stats if isinstance(stats, dict) else {}, hrv, max_metrics)
        batch.warnings.extend(check_daily(daily))
        batch.daily.append(daily)

    @staticmethod
    def _call(method: Callable[[str], Any], cdate: str) -> Any:
        return call_garmin(method, cdate)


def call_garmin(method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call one library method, translating its errors into ours.

    Missing data (404) is normal and returns None; a rate limit stops the run;
    anything else means the source is unusable right now. We look at the
    exception's class *name* so that this file never imports the library.
    """
    try:
        return method(*args, **kwargs)
    except Exception as exc:
        name = type(exc).__name__
        if "NotFound" in name:
            return None
        if "TooManyRequests" in name:
            raise HealthRateLimitedError("Garmin rate limit") from None
        logger.warning("Garmin call %s failed: %s", getattr(method, "__name__", "?"), name)
        raise HealthProviderError(f"Garmin request failed: {name}") from None
