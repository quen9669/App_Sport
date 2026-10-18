"""Tools for the longevity coach: daily activity, VO2max, heart-rate zones, smoke-free days.

Like the other tools, they reuse the app's own numbers (the Santé page) and
send summaries, never raw streams or positions.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.coach.tools.activities import _period, _visible
from app.coach.tools.base import NoInput, Tool, ToolContext, Weeks
from app.db.models import Activity, DailyHealth
from app.repositories import profile as profile_repo
from app.repositories import smoking as smoking_repo
from app.services.classification import Category, effective_category
from app.services.health_dashboard import health_days, weekly_intensity, weekly_steps
from app.services.smoking import DEFAULT_QUIT_DATE, CigaretteDay, summarize
from app.services.training_load import heart_rate_params
from app.services.weeks import Week, current_week

# Upper bound of each zone, in % of max heart rate (the common 5-zone model).
ZONES = [("z1", 60), ("z2", 70), ("z3", 80), ("z4", 90), ("z5", 101)]


def _weeks(ctx: ToolContext, count: int) -> list[Week]:
    weeks = [current_week(ctx.timezone, ctx.now)]
    while len(weeks) < count:
        weeks.insert(0, weeks[0].previous())
    return weeks


def get_daily_activity(ctx: ToolContext, args: Weeks) -> dict[str, Any]:
    weeks = _weeks(ctx, args.weeks)
    steps = weekly_steps(ctx.db, weeks)
    intensity = weekly_intensity(ctx.db, weeks)
    recent = health_days(ctx.db, ctx.today - timedelta(days=13), ctx.today, ctx.timezone)
    return {
        "weeks": [
            {
                "week": s.week.label,
                "steps_per_day": s.steps_per_day,  # average of the days with data
                "days_with_steps": s.step_days,
                "floors_climbed": s.floors_ascended if s.floor_days else None,
                "intensity_minutes": i.total if i.days else None,  # vigorous count double
            }
            for s, i in zip(steps, intensity, strict=True)
        ],
        "last_14_days_steps": [
            {"date": d.day.isoformat(), "steps": d.steps} for d in recent if d.steps is not None
        ],
        "note": "Intensity minutes follow the WHO count (150-300 per week recommended). "
        "The current week is in progress.",
    }


class VO2Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=180, ge=14, le=730, description="Number of days back from today.")


def get_vo2max_trend(ctx: ToolContext, args: VO2Input) -> dict[str, Any]:
    since = ctx.today - timedelta(days=args.days - 1)
    rows = ctx.db.scalars(
        select(DailyHealth)
        .where(DailyHealth.day >= since, DailyHealth.vo2max.is_not(None))
        .order_by(DailyHealth.day)
    ).all()
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        assert row.vo2max is not None  # filtered in the query
        by_month[f"{row.day:%Y-%m}"].append(row.vo2max)
    return {
        "period_days": args.days,
        "readings": len(rows),
        "latest": {"date": rows[-1].day.isoformat(), "vo2max": rows[-1].vo2max} if rows else None,
        "monthly_average": {
            month: round(sum(values) / len(values), 1) for month, values in by_month.items()
        },
        "note": "Garmin's estimate from runs with heart rate; trends over months matter more "
        "than one value.",
    }


def get_heart_rate_zones(ctx: ToolContext, args: Weeks) -> dict[str, Any]:
    weeks = _weeks(ctx, args.weeks)
    start, _ = _period(ctx, (ctx.today - weeks[0].monday).days + 1)
    _, end = _period(ctx, 1)
    params = heart_rate_params(ctx.db, ctx.today)
    totals = {
        week.label: {"z1": 0.0, "z2": 0.0, "z3": 0.0, "z4": 0.0, "z5": 0.0, "no_hr": 0.0}
        for week in weeks
    }
    for activity in _visible(ctx, start, end):
        if effective_category(activity) not in {Category.CARDIO, Category.TRANSPORT}:
            continue
        week = next((w for w in weeks if w.monday <= _local_day(ctx, activity) <= w.sunday), None)
        if week is None:
            continue
        minutes = (activity.moving_time_s or activity.elapsed_time_s) / 60
        totals[week.label][_zone(activity.average_heartrate, params.max_hr)] += minutes
    return {
        "max_heartrate": params.max_hr,
        "max_heartrate_source": params.max_source,
        "zones_percent_of_max": "z1 <60, z2 60-70, z3 70-80, z4 80-90, z5 >90",
        "minutes_per_week": {
            label: {zone: round(value) for zone, value in zones.items()}
            for label, zones in totals.items()
        },
        "note": "Approximation: each cardio activity (walks included) is put in ONE zone from "
        "its AVERAGE heart rate, not second by second. Say so when you use it.",
    }


def _local_day(ctx: ToolContext, activity: Activity) -> date:
    return activity.start_time.astimezone(ZoneInfo(ctx.timezone)).date()


def _zone(average_hr: float | None, max_hr: int | None) -> str:
    if not average_hr or not max_hr:
        return "no_hr"
    percent = 100 * average_hr / max_hr
    return next(name for name, upper in ZONES if percent < upper)


def get_smoke_free(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    saved = profile_repo.get_or_create_profile(ctx.db).smoke_free_since
    rows = smoking_repo.list_days(ctx.db)
    summary = summarize(
        saved or DEFAULT_QUIT_DATE,
        ctx.today,
        [CigaretteDay(r.day, r.cigarettes) for r in rows],  # notes stay in the app
    )
    return {
        "quit_date": summary.quit_date.isoformat(),
        "days_since_quit": summary.days_since_quit,
        "smoke_free_days": summary.smoke_free_days,
        "days_with_cigarettes": summary.cigarette_days,
        "cigarettes_since_quit": summary.cigarettes,
        "current_streak_days": summary.current_streak,
        "longest_streak_days": summary.longest_streak,
        "months": [vars(m) for m in summary.months],
        "note": "Only cigarettes are tracked; FRANKS still vapes (not tracked).",
    }


TOOLS = [
    Tool(
        "get_daily_activity",
        "Steps per day, floors climbed and Garmin intensity minutes per ISO week, plus the "
        "daily steps of the last 14 days.",
        "lit tes pas et ton activité",
        Weeks,
        get_daily_activity,
    ),
    Tool(
        "get_vo2max_trend",
        "Garmin VO2max estimates: latest value and monthly averages.",
        "lit ta VO2max",
        VO2Input,
        get_vo2max_trend,
    ),
    Tool(
        "get_heart_rate_zones",
        "Cardio minutes per week in each heart-rate zone (z2 = 60-70 % of max HR), "
        "approximated from each activity's average heart rate.",
        "calcule tes zones cardio",
        Weeks,
        get_heart_rate_zones,
    ),
    Tool(
        "get_smoke_free",
        "Smoke-free tracking since the quit date: smoke-free days, streaks, cigarettes per month.",
        "regarde tes jours sans cigarette",
        NoInput,
        get_smoke_free,
    ),
]
