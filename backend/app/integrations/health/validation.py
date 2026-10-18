"""Plausibility bounds shared by every health source.

A value outside these bounds is almost certainly a sensor or parsing error, so
it is dropped (set to ``None``) rather than stored and later trusted by charts
or coaches.
"""

from app.integrations.health.provider import DailyHealthRecord, SleepRecord

MAX_SLEEP_S = 16 * 3600


def _in_range(value: float | None, low: float, high: float) -> bool:
    return value is None or low <= value <= high


def check_sleep(record: SleepRecord) -> list[str]:
    """Return problems found, and clear the implausible fields in place."""
    problems: list[str] = []
    checks: list[tuple[str, float, float]] = [
        ("duration_s", 0, MAX_SLEEP_S),
        ("deep_s", 0, MAX_SLEEP_S),
        ("light_s", 0, MAX_SLEEP_S),
        ("rem_s", 0, MAX_SLEEP_S),
        ("awake_s", 0, MAX_SLEEP_S),
        ("score", 0, 100),
        ("resting_heartrate", 25, 120),
        ("hrv_ms", 5, 300),
        ("body_battery_wake", 0, 100),
    ]
    for name, low, high in checks:
        value = getattr(record, name)
        if not _in_range(value, low, high):
            problems.append(f"{record.night_date}: {name}={value} out of range, ignored")
            setattr(record, name, None)
    return problems


def check_daily(record: DailyHealthRecord) -> list[str]:
    problems: list[str] = []
    checks: list[tuple[str, float, float]] = [
        ("resting_heartrate", 25, 120),
        ("hrv_ms", 5, 300),
        ("stress_avg", 0, 100),
        ("steps", 0, 150_000),
        ("vo2max", 10, 95),
        ("body_battery_max", 0, 100),
        ("body_battery_min", 0, 100),
    ]
    for name, low, high in checks:
        value = getattr(record, name)
        if not _in_range(value, low, high):
            problems.append(f"{record.day}: {name}={value} out of range, ignored")
            setattr(record, name, None)
    return problems
