"""Plan B: import health data from files instead of the Garmin library.

Two formats are accepted:

1. **Our simple CSV** (one row per day, any column may be empty)::

       date,sleep_duration_min,sleep_score,deep_min,light_min,rem_min,awake_min,resting_hr,hrv_ms,body_battery_wake,steps,stress_avg,vo2max
       2026-10-17,452,81,95,240,98,19,49,62,85,10423,28,52.5

   A template lives in ``docs/templates/health-import-template.csv``. You can
   fill it from Garmin Connect's reports or any other tool.

2. **Garmin's data export** (Account > Data Management > Export Your Data):
   the ``*_sleepData.json`` files of the archive. ⚠️ The format of this export
   is not documented by Garmin; this parser follows the files observed so far
   and ignores what it does not understand. It will be checked against a real
   export of yours.

Rows that cannot be read are reported as warnings; the others are imported.
"""

import csv
import io
import json
from datetime import UTC, date, datetime
from typing import Any

from app.db.models.enums import DataSource
from app.integrations.health.provider import (
    DailyHealthRecord,
    HealthBatch,
    HealthProviderError,
    SleepRecord,
)
from app.integrations.health.validation import check_daily, check_sleep

CSV_COLUMNS = (
    "date",
    "sleep_duration_min",
    "sleep_score",
    "deep_min",
    "light_min",
    "rem_min",
    "awake_min",
    "resting_hr",
    "hrv_ms",
    "body_battery_wake",
    "steps",
    "stress_avg",
    "vo2max",
)
_SLEEP_COLUMNS = (
    "sleep_duration_min",
    "sleep_score",
    "deep_min",
    "light_min",
    "rem_min",
    "awake_min",
)
_DAILY_COLUMNS = ("steps", "stress_avg", "vo2max")


class FileImportProvider:
    """A provider whose data comes from one uploaded file."""

    source: str = DataSource.FILE_IMPORT

    def __init__(self, filename: str, content: bytes) -> None:
        self._batch = parse_file(filename, content)

    def fetch_range(self, start: date, end: date) -> HealthBatch:
        """Return the file's records within [start, end]."""
        return HealthBatch(
            sleep=[s for s in self._batch.sleep if start <= s.night_date <= end],
            daily=[d for d in self._batch.daily if start <= d.day <= end],
            warnings=list(self._batch.warnings),
        )

    def fetch_all(self) -> HealthBatch:
        return self._batch


def parse_file(filename: str, content: bytes) -> HealthBatch:
    """Pick the right parser from the file name, then validate every record."""
    try:
        text = content.decode("utf-8-sig")  # "-sig" removes the BOM Excel adds
    except UnicodeDecodeError:
        raise HealthProviderError("The file is not UTF-8 text.") from None

    name = filename.lower()
    if name.endswith(".csv"):
        batch = parse_csv(text)
    elif name.endswith(".json"):
        batch = parse_garmin_sleep_export(text)
    else:
        raise HealthProviderError("Unsupported file type: use .csv or Garmin .json export files.")

    for sleep in batch.sleep:
        batch.warnings.extend(check_sleep(sleep))
    for daily in batch.daily:
        batch.warnings.extend(check_daily(daily))
    return batch


# --- CSV --------------------------------------------------------------------


def _optional_float(row: dict[str, str], column: str) -> float | None:
    value = (row.get(column) or "").strip().replace(",", ".")  # accept French decimals
    return float(value) if value else None


def _optional_int(row: dict[str, str], column: str) -> int | None:
    value = _optional_float(row, column)
    return int(round(value)) if value is not None else None


def _minutes_to_s(row: dict[str, str], column: str) -> int | None:
    value = _optional_float(row, column)
    return int(round(value * 60)) if value is not None else None


def parse_csv(text: str) -> HealthBatch:
    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    if "date" not in columns:
        raise HealthProviderError("CSV must have a 'date' column (see the template).")
    unknown = columns - set(CSV_COLUMNS)

    batch = HealthBatch()
    if unknown:
        batch.warnings.append(f"Ignored unknown columns: {', '.join(sorted(unknown))}")
    # Line 1 is the header, so data starts at line 2.
    for line_number, row in enumerate(reader, start=2):
        try:
            _add_csv_row(row, batch)
        except ValueError as exc:
            batch.warnings.append(f"line {line_number}: {exc}")
    return batch


def _add_csv_row(row: dict[str, str], batch: HealthBatch) -> None:
    day = date.fromisoformat((row.get("date") or "").strip())
    resting_hr = _optional_int(row, "resting_hr")
    hrv = _optional_float(row, "hrv_ms")

    if any((row.get(column) or "").strip() for column in _SLEEP_COLUMNS):
        batch.sleep.append(
            SleepRecord(
                night_date=day,
                duration_s=_minutes_to_s(row, "sleep_duration_min"),
                score=_optional_int(row, "sleep_score"),
                deep_s=_minutes_to_s(row, "deep_min"),
                light_s=_minutes_to_s(row, "light_min"),
                rem_s=_minutes_to_s(row, "rem_min"),
                awake_s=_minutes_to_s(row, "awake_min"),
                resting_heartrate=resting_hr,
                hrv_ms=hrv,
                body_battery_wake=_optional_int(row, "body_battery_wake"),
                raw=dict(row),
            )
        )
    has_daily_values = any((row.get(column) or "").strip() for column in _DAILY_COLUMNS)
    if has_daily_values or resting_hr is not None or hrv is not None:
        batch.daily.append(
            DailyHealthRecord(
                day=day,
                resting_heartrate=resting_hr,
                hrv_ms=hrv,
                stress_avg=_optional_int(row, "stress_avg"),
                steps=_optional_int(row, "steps"),
                vo2max=_optional_float(row, "vo2max"),
                raw=dict(row),
            )
        )


# --- Garmin export JSON -----------------------------------------------------


def _parse_garmin_time(value: Any) -> datetime | None:
    """Export timestamps look like "2026-10-16T22:41:00.0" (GMT, without timezone)."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


def _whole_number(value: Any) -> int | None:
    """Keep only real numbers: anything else in the export becomes None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def parse_garmin_sleep_export(text: str) -> HealthBatch:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HealthProviderError("Invalid JSON file.") from None
    if not isinstance(data, list):
        raise HealthProviderError("Expected a Garmin *_sleepData.json file (a JSON list).")

    batch = HealthBatch()
    for index, entry in enumerate(data):
        if not isinstance(entry, dict) or "calendarDate" not in entry:
            batch.warnings.append(f"entry {index}: no calendarDate, skipped")
            continue
        try:
            night = date.fromisoformat(entry["calendarDate"])
        except (TypeError, ValueError):
            batch.warnings.append(f"entry {index}: invalid calendarDate, skipped")
            continue
        deep, light, rem = (
            _whole_number(entry.get(key))
            for key in ("deepSleepSeconds", "lightSleepSeconds", "remSleepSeconds")
        )
        asleep = sum(phase for phase in (deep, light, rem) if phase is not None)
        scores = entry.get("sleepScores")
        batch.sleep.append(
            SleepRecord(
                night_date=night,
                sleep_start=_parse_garmin_time(entry.get("sleepStartTimestampGMT")),
                sleep_end=_parse_garmin_time(entry.get("sleepEndTimestampGMT")),
                duration_s=asleep or None,
                score=_whole_number(scores.get("overallScore"))
                if isinstance(scores, dict)
                else None,
                deep_s=deep,
                light_s=light,
                rem_s=rem,
                awake_s=_whole_number(entry.get("awakeSleepSeconds")),
                raw=entry,
            )
        )
    return batch
