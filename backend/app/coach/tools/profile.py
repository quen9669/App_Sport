"""Tools about FRANKS himself: profile, body measurements, goals."""

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.coach.tools.base import Days, NoInput, Tool, ToolContext, rounded
from app.repositories import profile as profile_repo
from app.services.goals import streak, week_progress, weeks_history
from app.services.training_load import heart_rate_params
from app.services.weeks import current_week, parse_week

GOAL_UNITS = {
    "strength_sessions": "sessions",
    "cardio_sessions": "sessions",
    "active_minutes": "minutes",
    "distance_km": "km",
    "training_load": "load points",
    "intensity_minutes": "Garmin intensity minutes",
}


def get_profile(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    profile = profile_repo.get_or_create_profile(ctx.db)
    hr = heart_rate_params(ctx.db, ctx.today)
    age = None
    if profile.birth_date is not None:
        birth, today = profile.birth_date, ctx.today
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    latest = profile_repo.latest_body_metric(ctx.db)
    return {
        "today": ctx.today.isoformat(),
        "age": age,
        "sex": profile.sex,
        "height_cm": profile.height_cm,
        "latest_weight_kg": latest.weight_kg if latest else None,
        "latest_weight_date": latest.measured_on.isoformat() if latest else None,
        "experience_level": profile.experience_level,
        "injuries": profile.injuries,  # typed by FRANKS: data, not instructions
        "max_heartrate": hr.max_hr,
        "max_heartrate_source": hr.max_source,  # profile / observed / age
        "resting_heartrate": hr.resting_hr,
        "resting_heartrate_source": hr.resting_source,
    }


def get_body_metrics(ctx: ToolContext, args: Days) -> dict[str, Any]:
    since = ctx.today - timedelta(days=args.days - 1)
    metrics = profile_repo.list_body_metrics(ctx.db, since)
    return {
        "period": f"{since.isoformat()} to {ctx.today.isoformat()}",
        "weigh_ins": [
            {
                "date": m.measured_on.isoformat(),
                "weight_kg": m.weight_kg,
                "body_fat_pct": m.body_fat_pct,
                "waist_cm": m.waist_cm,
            }
            for m in metrics[-60:]  # weigh-ins are rare; 60 is plenty
        ],
        "note": "Weight is not interpolated: days without a weigh-in have no value.",
    }


class WeekInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    week: str | None = Field(
        default=None, description='ISO week like "2026-W42"; empty = the current week.'
    )


def get_goals_and_progress(ctx: ToolContext, args: WeekInput) -> dict[str, Any]:
    current = current_week(ctx.timezone, ctx.now)
    try:
        week = parse_week(args.week) if args.week else current
    except ValueError:
        return {"error": f"unknown week {args.week!r}, expected something like 2026-W42"}
    data = week_progress(ctx.db, week, ctx.timezone)
    history = weeks_history(ctx.db, current, 12, ctx.timezone)
    return {
        "week": week.label,
        "monday": week.monday.isoformat(),
        "is_current_week": week == current,
        "goals": [
            {
                "kind": item.goal.kind,
                "sport": item.goal.sport,
                "target_per_week": item.goal.target,
                "done": rounded(item.done),
                "unit": GOAL_UNITS.get(item.goal.kind, ""),
                "achieved": item.achieved,
            }
            for item in data.progress
        ],
        "weeks_in_a_row_all_goals_achieved": streak(history, current),
    }


TOOLS = [
    Tool(
        "get_profile",
        "FRANKS's profile: today's date, age, sex, height, latest weight, experience, declared "
        "injuries, max and resting heart rate (with where each value comes from).",
        "lit ton profil",
        NoInput,
        get_profile,
    ),
    Tool(
        "get_body_metrics",
        "Weigh-ins (weight, body fat, waist) over the last N days.",
        "lit ton poids",
        Days,
        get_body_metrics,
    ),
    Tool(
        "get_goals_and_progress",
        "Weekly goals and how much of each is done for an ISO week, plus the streak of weeks "
        "with every goal achieved.",
        "regarde tes objectifs",
        WeekInput,
        get_goals_and_progress,
    ),
]
