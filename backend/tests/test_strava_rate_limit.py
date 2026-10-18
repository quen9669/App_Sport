"""Tests for Strava quota handling, with a fake clock (no real waiting)."""

from datetime import UTC, datetime

import pytest

from app.integrations.strava.rate_limit import (
    DailyLimitReachedError,
    RateLimiter,
    seconds_until_next_window,
)

NOW = datetime(2026, 10, 18, 10, 7, 30, tzinfo=UTC)


def make_limiter() -> tuple[RateLimiter, list[float]]:
    sleeps: list[float] = []
    return RateLimiter(sleep=sleeps.append, now=lambda: NOW), sleeps


def test_next_window_is_next_quarter_hour() -> None:
    # 10:07:30 -> 10:15:00 is 450 s, plus 1 s of slack.
    assert seconds_until_next_window(NOW) == 451
    assert seconds_until_next_window(datetime(2026, 1, 1, 23, 59, tzinfo=UTC)) == 61


def test_no_wait_when_far_from_limits() -> None:
    limiter, sleeps = make_limiter()
    limiter.update_from_headers(
        {"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "10,50"}
    )

    limiter.before_request()

    assert sleeps == []


def test_waits_for_next_window_near_15_minute_limit() -> None:
    limiter, sleeps = make_limiter()
    limiter.update_from_headers(
        {"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "97,300"}
    )

    limiter.before_request()

    assert sleeps == [451]


def test_stops_near_daily_limit() -> None:
    limiter, _ = make_limiter()
    limiter.update_from_headers(
        {"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "3,996"}
    )

    with pytest.raises(DailyLimitReachedError):
        limiter.before_request()


def test_tightest_header_family_wins() -> None:
    # Overall usage is low, but the read-specific quota is almost used up.
    limiter, sleeps = make_limiter()
    limiter.update_from_headers(
        {
            "X-RateLimit-Limit": "200,2000",
            "X-RateLimit-Usage": "97,300",
            "X-ReadRateLimit-Limit": "100,1000",
            "X-ReadRateLimit-Usage": "97,300",
        }
    )

    limiter.before_request()

    assert sleeps == [451]


def test_malformed_headers_are_ignored() -> None:
    limiter, sleeps = make_limiter()
    limiter.update_from_headers({"X-RateLimit-Limit": "oops", "X-RateLimit-Usage": "1"})

    limiter.before_request()

    assert sleeps == []
