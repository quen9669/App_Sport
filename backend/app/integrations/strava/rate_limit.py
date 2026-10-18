"""Respect Strava's API quotas.

Strava counts requests in two windows and sends the counters in every response:

- ``X-RateLimit-Limit: 200,2000`` / ``X-RateLimit-Usage: 12,345``: all requests,
  per 15 minutes and per day;
- ``X-ReadRateLimit-Limit: 100,1000`` / ``X-ReadRateLimit-Usage: ...``: read
  requests only (what we do), usually the tighter one.

The 15-minute windows reset at :00, :15, :30 and :45; the daily one at midnight UTC.

Strategy: after each response we remember the counters. Before the next
request, if we are close to the 15-minute limit we wait until the window
resets; if we are close to the daily limit we stop the sync (it resumes on the
next scheduled run) by raising :class:`DailyLimitReachedError`.
"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Keep a few requests in reserve so that we never actually hit a 429.
SAFETY_MARGIN = 5


class DailyLimitReachedError(RuntimeError):
    """The daily quota is (almost) used up: stop and resume tomorrow."""


@dataclass
class _Window:
    limit: int
    usage: int


def _parse_pair(value: str | None) -> tuple[int, int] | None:
    """Parse "12,345" into (12, 345). Returns None if the header is absent or malformed."""
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def seconds_until_next_window(now: datetime) -> float:
    """Seconds until the next quarter hour (:00, :15, :30, :45), plus 1 second of slack."""
    next_quarter_minute = (now.minute // 15 + 1) * 15
    window_start = now.replace(minute=0, second=0, microsecond=0)
    next_window = window_start + timedelta(minutes=next_quarter_minute)
    return (next_window - now).total_seconds() + 1


class RateLimiter:
    """Tracks Strava quota usage and waits or stops before hitting the limits.

    ``sleep`` and ``now`` are injectable so tests run instantly with a fake clock.
    """

    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sleep = sleep
        self._now = now
        self._short: _Window | None = None  # 15-minute window
        self._daily: _Window | None = None

    def update_from_headers(self, headers: Mapping[str, str]) -> None:
        """Record the counters of a response, keeping the tightest of the two header families."""
        windows: list[tuple[_Window, _Window]] = []
        for prefix in ("X-RateLimit", "X-ReadRateLimit"):
            limits = _parse_pair(headers.get(f"{prefix}-Limit"))
            usages = _parse_pair(headers.get(f"{prefix}-Usage"))
            if limits and usages:
                windows.append((_Window(limits[0], usages[0]), _Window(limits[1], usages[1])))
        if not windows:
            return
        # "Tightest" = fewest requests remaining.
        self._short = min((w[0] for w in windows), key=lambda w: w.limit - w.usage)
        self._daily = min((w[1] for w in windows), key=lambda w: w.limit - w.usage)

    def before_request(self) -> None:
        """Call before every request: may raise (daily) or sleep (15 minutes)."""
        if self._daily and self._daily.usage >= self._daily.limit - SAFETY_MARGIN:
            raise DailyLimitReachedError("Strava daily quota almost used up; resuming next run.")
        if self._short and self._short.usage >= self._short.limit - SAFETY_MARGIN:
            self.wait_for_next_window()

    def wait_for_next_window(self) -> None:
        """Sleep until the 15-minute window resets, then forget the old counters."""
        self._sleep(seconds_until_next_window(self._now()))
        self._short = None
