"""Smoke-free counters: days without a cigarette since the quit date, streaks.

Only the days with a cigarette are stored; every other day since the quit date
counts as smoke-free, today included (the day is not over, but nothing was
written for it). Pure functions on dates: easy to test, no database here.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

# FRANKS stopped cigarettes at the beginning of September 2026 (vaping only
# since). Used until a quit date is saved in the profile.
DEFAULT_QUIT_DATE = date(2026, 9, 1)


@dataclass
class CigaretteDay:
    day: date
    cigarettes: int
    note: str | None = None


@dataclass
class MonthSummary:
    month: str  # "2026-09"
    days: int  # days of that month since the quit date, up to today
    smoke_free_days: int
    cigarettes: int


@dataclass
class SmokeFreeSummary:
    quit_date: date
    today: date
    days_since_quit: int  # today included; 0 if the quit date is in the future
    smoke_free_days: int
    cigarette_days: int
    cigarettes: int  # total since the quit date
    current_streak: int  # smoke-free days in a row, up to today
    longest_streak: int
    months: list[MonthSummary] = field(default_factory=list)


def summarize(quit_date: date, today: date, entries: Iterable[CigaretteDay]) -> SmokeFreeSummary:
    """The counters for the period from `quit_date` to `today` (both included).

    Days with a cigarette before the quit date (an older attempt) or after
    today (a typo) are ignored here, but stay in the database.
    """
    in_period = sorted((e for e in entries if quit_date <= e.day <= today), key=lambda e: e.day)
    days_since_quit = max((today - quit_date).days + 1, 0)
    return SmokeFreeSummary(
        quit_date=quit_date,
        today=today,
        days_since_quit=days_since_quit,
        smoke_free_days=days_since_quit - len(in_period),
        cigarette_days=len(in_period),
        cigarettes=sum(e.cigarettes for e in in_period),
        current_streak=_current_streak(quit_date, today, in_period),
        longest_streak=_longest_streak(quit_date, today, in_period),
        months=_months(quit_date, today, in_period),
    )


def _current_streak(quit_date: date, today: date, entries: list[CigaretteDay]) -> int:
    if today < quit_date:
        return 0
    if not entries:
        return (today - quit_date).days + 1
    # Days after the last cigarette, up to today: 0 if it was today.
    return (today - entries[-1].day).days


def _longest_streak(quit_date: date, today: date, entries: list[CigaretteDay]) -> int:
    """The longest run of days between two cigarettes (or the period's ends)."""
    if today < quit_date:
        return 0
    longest = 0
    run_start = quit_date  # first smoke-free day of the current run
    for entry in entries:
        longest = max(longest, (entry.day - run_start).days)
        run_start = entry.day + timedelta(days=1)
    return max(longest, (today - run_start).days + 1)


def _months(quit_date: date, today: date, entries: list[CigaretteDay]) -> list[MonthSummary]:
    """One line per calendar month, from the quit month to the current one."""
    months: list[MonthSummary] = []
    start = quit_date
    while start <= today:
        next_month = (start.replace(day=1) + timedelta(days=32)).replace(day=1)
        end = min(next_month - timedelta(days=1), today)
        inside = [e for e in entries if start <= e.day <= end]
        days = (end - start).days + 1
        months.append(
            MonthSummary(
                month=start.strftime("%Y-%m"),
                days=days,
                smoke_free_days=days - len(inside),
                cigarettes=sum(e.cigarettes for e in inside),
            )
        )
        start = next_month
    return months
