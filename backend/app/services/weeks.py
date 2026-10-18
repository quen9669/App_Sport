"""Training weeks: Monday 00:00 to Sunday 23:59:59, in the user's local time.

Activities are stored in UTC, but "this week" is a local notion: a run on
Sunday at 23:30 in Luxembourg is 21:30 or 22:30 UTC depending on summer or
winter time, and must count for that Sunday's week. So we compute the local
boundaries first, then convert them to UTC to query the database.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")


@dataclass(frozen=True)
class Week:
    year: int  # ISO year (can differ from the calendar year around 1 January)
    number: int  # ISO week number, 1 to 52 or 53

    @property
    def label(self) -> str:
        """ISO 8601 notation, e.g. "2026-W42"."""
        return f"{self.year}-W{self.number:02d}"

    @property
    def monday(self) -> date:
        return date.fromisocalendar(self.year, self.number, 1)

    @property
    def sunday(self) -> date:
        return self.monday + timedelta(days=6)

    def utc_range(self, timezone: str) -> tuple[datetime, datetime]:
        """[start, end) in UTC: local Monday 00:00 to the next local Monday 00:00.

        Each boundary is converted on its own, so a week containing a daylight
        saving change is simply 167 or 169 hours long: nothing is lost.
        """
        zone = ZoneInfo(timezone)
        start = datetime.combine(self.monday, time(0), tzinfo=zone)
        end = datetime.combine(self.monday + timedelta(days=7), time(0), tzinfo=zone)
        return start.astimezone(UTC), end.astimezone(UTC)

    def previous(self) -> "Week":
        return week_of(self.monday - timedelta(days=7))


def week_of(day: date) -> Week:
    iso = day.isocalendar()
    return Week(iso.year, iso.week)


def current_week(timezone: str, now: datetime | None = None) -> Week:
    """The week we are in right now, in the user's timezone."""
    moment = now or datetime.now(UTC)
    return week_of(moment.astimezone(ZoneInfo(timezone)).date())


def parse_week(label: str) -> Week:
    """Read "2026-W42". Raises ValueError for anything else (e.g. week 54)."""
    match = _WEEK_PATTERN.match(label)
    if match is None:
        raise ValueError("Week must look like 2026-W42")
    year, number = int(match.group(1)), int(match.group(2))
    date.fromisocalendar(year, number, 1)  # raises ValueError if the week does not exist
    return Week(year, number)
