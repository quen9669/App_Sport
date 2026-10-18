"""The common "contract" every health data source must follow.

Why an interface? The Garmin library is unofficial and may break any day.
Isolating it behind ``HealthDataProvider`` means that if it breaks, only one
file is affected and the app keeps working with file imports.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol


@dataclass
class SleepRecord:
    """One night of sleep. ``night_date`` = date of the morning you wake up."""

    night_date: date
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    duration_s: int | None = None
    score: int | None = None
    deep_s: int | None = None
    light_s: int | None = None
    rem_s: int | None = None
    awake_s: int | None = None
    resting_heartrate: int | None = None
    hrv_ms: float | None = None
    body_battery_wake: int | None = None
    # The original data, kept in the raw_payload table.
    raw: Any = None


@dataclass
class DailyHealthRecord:
    """Health metrics of one calendar day."""

    day: date
    resting_heartrate: int | None = None
    hrv_ms: float | None = None
    stress_avg: int | None = None
    steps: int | None = None
    vo2max: float | None = None
    body_battery_max: int | None = None
    body_battery_min: int | None = None
    intensity_moderate_min: int | None = None
    intensity_vigorous_min: int | None = None
    floors_ascended: int | None = None
    floors_descended: int | None = None
    raw: Any = None


@dataclass
class WeightRecord:
    """One weigh-in (e.g. from a Garmin Index scale or typed in Garmin Connect)."""

    day: date
    weight_kg: float
    body_fat_pct: float | None = None
    raw: Any = None


@dataclass
class HealthBatch:
    """What a provider returns: nights and days, plus problems it met along the way."""

    sleep: list[SleepRecord] = field(default_factory=list)
    daily: list[DailyHealthRecord] = field(default_factory=list)
    weights: list[WeightRecord] = field(default_factory=list)
    # Human-readable, secret-free messages (e.g. "line 12: invalid date").
    warnings: list[str] = field(default_factory=list)


class HealthProviderError(RuntimeError):
    """The source cannot be used right now (login refused, library broken...)."""


class HealthRateLimitedError(HealthProviderError):
    """The source asks us to slow down: stop now and resume at the next run."""


class HealthDataProvider(Protocol):
    """Anything with a ``source`` name and a ``fetch_range`` method is a provider.

    ``Protocol`` means "duck typing, checked by mypy": providers don't need to
    inherit from this class, they just need the same attributes and methods.
    """

    source: str

    def fetch_range(self, start: date, end: date) -> HealthBatch:
        """Return the data between ``start`` and ``end`` (both included)."""
        ...
