"""Tests for the health providers: Garmin mapping and file import (plan B)."""

from datetime import date

import pytest

from app.integrations.health.file_import import parse_file
from app.integrations.health.garmin_connect import GarminConnectProvider, map_sleep
from app.integrations.health.provider import HealthProviderError
from tests.fixtures.garmin import FakeGarmin, sleep_payload

DAY = date(2026, 10, 17)


def test_map_sleep_reads_garmin_fields() -> None:
    record = map_sleep(DAY, sleep_payload(DAY, hours=7.5, score=82))

    assert record is not None
    assert record.duration_s == 27_000
    assert record.score == 82
    assert record.resting_heartrate == 49
    assert record.hrv_ms == 61.0
    assert record.sleep_end is not None and record.sleep_end.tzinfo is not None


def test_map_sleep_returns_none_for_night_without_sleep() -> None:
    assert map_sleep(DAY, {"dailySleepDTO": {"sleepTimeSeconds": None}}) is None
    assert map_sleep(DAY, {}) is None


def test_garmin_provider_fetches_each_day() -> None:
    fake = FakeGarmin()
    provider = GarminConnectProvider(login=lambda: fake)

    batch = provider.fetch_range(date(2026, 10, 15), DAY)

    assert [s.night_date for s in batch.sleep] == [date(2026, 10, 15), date(2026, 10, 16), DAY]
    assert batch.daily[0].steps == 10423
    assert (batch.daily[0].floors_ascended, batch.daily[0].floors_descended) == (12, 10)
    assert batch.daily[0].vo2max == 52.4
    assert batch.warnings == []


def test_garmin_provider_logs_in_only_when_used() -> None:
    logins: list[int] = []

    def login() -> FakeGarmin:
        logins.append(1)
        return FakeGarmin()

    provider = GarminConnectProvider(login=login)
    assert logins == []
    provider.fetch_range(DAY, DAY)
    provider.fetch_range(DAY, DAY)
    assert logins == [1]


def test_garmin_rate_limit_keeps_what_was_fetched() -> None:
    fake = FakeGarmin()
    fake.rate_limit_from = date(2026, 10, 16)

    batch = GarminConnectProvider(login=lambda: fake).fetch_range(date(2026, 10, 14), DAY)

    assert len(batch.sleep) == 2
    assert any("rate limit" in w for w in batch.warnings)


def test_garmin_broken_library_raises_provider_error() -> None:
    fake = FakeGarmin()
    fake.broken = True

    with pytest.raises(HealthProviderError):
        GarminConnectProvider(login=lambda: fake).fetch_range(DAY, DAY)


# --- File import ------------------------------------------------------------

CSV = (
    "date,sleep_duration_min,sleep_score,deep_min,light_min,rem_min,awake_min,"
    "resting_hr,hrv_ms,body_battery_wake,steps,stress_avg,vo2max\n"
    "2026-10-16,452,81,95,240,98,19,49,62,85,10423,28,52.5\n"
    "2026-10-17,,,,,,,51,,,8000,,\n"
    "not-a-date,400,70,,,,,,,,,,\n"
    '2026-10-18,430,250,90,240,90,10,48,"60,5",,,,\n'
)


def test_csv_import_reads_rows_and_reports_problems() -> None:
    batch = parse_file("health.csv", CSV.encode())

    assert [s.night_date for s in batch.sleep] == [date(2026, 10, 16), date(2026, 10, 18)]
    first = batch.sleep[0]
    assert first.duration_s == 452 * 60
    assert first.score == 81
    # Row 2 has no sleep values but daily ones.
    assert any(d.day == date(2026, 10, 17) and d.steps == 8000 for d in batch.daily)
    # Line 4 has an invalid date; line 5 has an impossible score of 250 (dropped).
    assert any(w.startswith("line 4") for w in batch.warnings)
    assert batch.sleep[1].score is None
    # French decimal comma accepted.
    assert batch.sleep[1].hrv_ms == 60.5


def test_csv_without_date_column_is_rejected() -> None:
    with pytest.raises(HealthProviderError, match="date"):
        parse_file("health.csv", b"day,steps\n2026-10-16,100\n")


def test_csv_with_excel_bom_is_accepted() -> None:
    batch = parse_file("health.csv", "﻿date,steps\n2026-10-16,100\n".encode())

    assert batch.daily[0].steps == 100


def test_garmin_export_json_is_parsed() -> None:
    content = b"""[
      {"calendarDate": "2026-10-16", "deepSleepSeconds": 5400, "lightSleepSeconds": 14400,
       "remSleepSeconds": 5400, "awakeSleepSeconds": 900,
       "sleepStartTimestampGMT": "2026-10-15T21:40:00.0",
       "sleepEndTimestampGMT": "2026-10-16T05:10:00.0",
       "sleepScores": {"overallScore": 84}},
      {"oops": true}
    ]"""

    batch = parse_file("2026_sleepData.json", content)

    assert len(batch.sleep) == 1
    assert batch.sleep[0].duration_s == 25_200
    assert batch.sleep[0].score == 84
    assert len(batch.warnings) == 1


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("data.txt", b"x"),
        ("data.json", b"{not json"),
        ("data.json", b'{"a": 1}'),
        ("d.csv", b"\xff\xfe"),
    ],
)
def test_bad_files_are_rejected(filename: str, content: bytes) -> None:
    with pytest.raises(HealthProviderError):
        parse_file(filename, content)
