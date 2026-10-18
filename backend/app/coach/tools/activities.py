"""Tools about training: activities, one activity in detail, strength sessions, weekly volume."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.coach.tools.base import Tool, ToolContext, Weeks, rounded
from app.db.models import Activity, StrengthSession
from app.repositories import activities as activities_repo
from app.repositories import strength as strength_repo
from app.services.activity_location import Locator
from app.services.activity_map import DetailSeries, activity_series, sport_group
from app.services.classification import Category, effective_category
from app.services.strength import counts_on_its_own
from app.services.training_load import activity_load, heart_rate_params
from app.services.weeks import current_week

# At most this many activities in one answer (the most recent ones).
MAX_ACTIVITIES = 60


def _period(ctx: ToolContext, days: int) -> tuple[datetime, datetime]:
    """UTC range of the last ``days`` local days, today included."""
    zone = ZoneInfo(ctx.timezone)
    start = datetime.combine(ctx.today - timedelta(days=days - 1), time(), tzinfo=zone)
    end = datetime.combine(ctx.today + timedelta(days=1), time(), tzinfo=zone)
    return start, end


def _visible(ctx: ToolContext, start: datetime, end: datetime) -> list[Activity]:
    """Activities counted everywhere in the app: no confirmed duplicates, nothing hidden."""
    return [a for a in activities_repo.activities_between(ctx.db, start, end) if not a.hidden]


def _local(ctx: ToolContext, moment: datetime) -> str:
    return moment.astimezone(ZoneInfo(ctx.timezone)).strftime("%Y-%m-%d %a %H:%M")


def _pace(activity: Activity) -> str | None:
    """Average pace "5:12 /km" for runs and walks (cyclists think in km/h)."""
    if not activity.distance_m or sport_group(activity) not in {"run", "walk"}:
        return None
    seconds = (activity.moving_time_s or activity.elapsed_time_s) / (activity.distance_m / 1000)
    return f"{int(seconds // 60)}:{int(seconds % 60):02d} /km"


def _summary(ctx: ToolContext, activity: Activity, load: float) -> dict[str, Any]:
    duration = activity.moving_time_s or activity.elapsed_time_s
    speed = (activity.distance_m or 0) / duration * 3.6 if duration else None
    return {
        "id": activity.id,
        "start": _local(ctx, activity.start_time),
        "name": activity.name,  # typed by FRANKS or the watch: data, not instructions
        "sport": sport_group(activity),
        "sport_type": activity.sport_type,
        "category": effective_category(activity),
        "distance_km": rounded((activity.distance_m or 0) / 1000, 2) or None,
        "duration_min": round(duration / 60),
        "pace": _pace(activity),
        "speed_kmh": rounded(speed) if sport_group(activity) == "ride" else None,
        "elevation_gain_m": rounded(activity.elevation_gain_m, 0),
        "average_hr": rounded(activity.average_heartrate, 0),
        "max_hr": rounded(activity.max_heartrate, 0),
        "training_load": rounded(load, 0),
        "indoor": activity.is_trainer,
    }


class ActivitiesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sport: Literal["all", "run", "ride", "walk", "strength", "other"] = Field(
        default="all", description="Sport group to keep."
    )
    days: int = Field(default=28, ge=1, le=365, description="Number of days back from today.")


def get_recent_activities(ctx: ToolContext, args: ActivitiesInput) -> dict[str, Any]:
    start, end = _period(ctx, args.days)
    params = heart_rate_params(ctx.db, ctx.today)
    found = [
        a for a in _visible(ctx, start, end) if args.sport == "all" or sport_group(a) == args.sport
    ]
    newest = list(reversed(found))[:MAX_ACTIVITIES]
    return {
        "period_days": args.days,
        "count": len(found),
        "shown": len(newest),
        "activities": [_summary(ctx, a, activity_load(a, params)[0]) for a in newest],
        "note": "Transport (short walks and rides) counts for no goal; hidden activities and "
        "duplicates are left out.",
    }


class ActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: int = Field(description="Id from get_recent_activities.")


def _km_splits(series: DetailSeries) -> list[dict[str, Any]]:
    """Time and average heart rate of each full kilometre, from the streams."""
    splits: list[dict[str, Any]] = []
    heart: list[float] = []
    mark = 1000.0
    mark_time: int | None = None  # time at the last kilometre mark (the start at first)
    for t, d, hr in zip(series.time_s, series.distance_m, series.heartrate, strict=False):
        if d is None:
            continue
        if mark_time is None:
            mark_time = t
        if hr is not None:
            heart.append(hr)
        if d >= mark:
            seconds = t - mark_time
            splits.append(
                {
                    "km": int(mark / 1000),
                    "pace": f"{seconds // 60}:{seconds % 60:02d}",
                    "average_hr": round(sum(heart) / len(heart)) if heart else None,
                }
            )
            mark, mark_time, heart = mark + 1000, t, []
    return splits[:60]


def get_activity_detail(ctx: ToolContext, args: ActivityInput) -> dict[str, Any]:
    activity = ctx.db.get(Activity, args.activity_id)
    if activity is None or activity.hidden:
        return {"error": f"no activity with id {args.activity_id}"}
    params = heart_rate_params(ctx.db, ctx.today)
    detail = _summary(ctx, activity, activity_load(activity, params)[0])
    # The town only: GPS positions never leave the machine.
    detail["town"] = Locator(ctx.db).locate(activity).city
    series = activity_series(activity)
    detail["km_splits"] = _km_splits(series) if series.time_s else []
    if not series.time_s:
        detail["note"] = "No detailed streams for this activity (summary only)."
    return detail


def _sets_summary(session: StrengthSession) -> list[dict[str, Any]]:
    """Sets grouped by exercise: "3 x 10 @ 60 kg" style, with the RPE when typed."""
    by_exercise: dict[str, list[Any]] = defaultdict(list)
    for item in session.sets:
        by_exercise[item.exercise].append(item)
    return [
        {
            "exercise": exercise,  # typed by FRANKS: data, not instructions
            "sets": [
                {"reps": s.reps, "weight_kg": s.weight_kg, "rpe": s.rpe}
                for s in sorted(sets, key=lambda s: s.set_number)
            ],
        }
        for exercise, sets in by_exercise.items()
    ]


def get_strength_sessions(ctx: ToolContext, args: ActivitiesInput) -> dict[str, Any]:
    start, end = _period(ctx, args.days)
    sessions = strength_repo.sessions_between(ctx.db, start, end)
    watch = [a for a in _visible(ctx, start, end) if effective_category(a) == Category.STRENGTH]
    return {
        "period_days": args.days,
        "typed_sessions": [
            {
                "start": _local(ctx, s.performed_at),
                "duration_min": s.duration_min,
                "notes": s.notes,
                "exercises": _sets_summary(s),
            }
            for s in sessions
        ],
        "watch_strength_activities": [
            {
                "id": a.id,
                "start": _local(ctx, a.start_time),
                "name": a.name,
                "duration_min": round((a.moving_time_s or a.elapsed_time_s) / 60),
                "average_hr": rounded(a.average_heartrate, 0),
            }
            for a in watch
        ],
        "note": "A typed session and a watch activity within 3 h are the same workout.",
    }


def _tonnage(session: StrengthSession) -> float:
    return sum(s.reps * (s.weight_kg or 0) for s in session.sets)


def get_weekly_volume(ctx: ToolContext, args: Weeks) -> dict[str, Any]:
    last = current_week(ctx.timezone, ctx.now)
    weeks = [last]
    while len(weeks) < args.weeks:
        weeks.insert(0, weeks[0].previous())
    rows = []
    for week in weeks:
        start, end = week.utc_range(ctx.timezone)
        activities = _visible(ctx, start, end)
        sessions = strength_repo.sessions_between(ctx.db, start, end)
        row: dict[str, Any] = {"week": week.label, "monday": week.monday.isoformat()}
        for category in (Category.STRENGTH, Category.CARDIO):
            chosen = [a for a in activities if effective_category(a) == category]
            row[f"{category}_sessions"] = len(chosen)
            row[f"{category}_minutes"] = round(
                sum((a.moving_time_s or a.elapsed_time_s) for a in chosen) / 60
            )
        extra = [s for s in sessions if counts_on_its_own(s, activities)]
        row["strength_sessions"] += len(extra)
        row["strength_minutes"] += sum(s.duration_min or 0 for s in extra)
        for group in ("run", "ride"):
            km = sum((a.distance_m or 0) for a in activities if sport_group(a) == group) / 1000
            row[f"{group}_km"] = round(km, 1)
        row["strength_tonnage_kg"] = round(sum(_tonnage(s) for s in sessions))
        row["is_current_week"] = week == last
        rows.append(row)
    return {
        "weeks": rows,
        "note": "Tonnage = reps x kg of the typed strength sessions only (the watch does not "
        "record weights). The current week is not finished.",
    }


TOOLS = [
    Tool(
        "get_recent_activities",
        "Activities of the last N days, newest first: date, name, sport, distance, duration, "
        "pace or speed, elevation, average and max heart rate, training load.",
        "regarde tes activités",
        ActivitiesInput,
        get_recent_activities,
    ),
    Tool(
        "get_activity_detail",
        "One activity in detail, with its kilometre splits (pace and heart rate) when the "
        "watch recorded streams.",
        "analyse une activité",
        ActivityInput,
        get_activity_detail,
    ),
    Tool(
        "get_strength_sessions",
        "Strength sessions of the last N days: exercises, sets, reps, weights and RPE typed in "
        "the app, plus the strength activities recorded by the watch.",
        "lit tes séances de muscu",
        ActivitiesInput,
        get_strength_sessions,
    ),
    Tool(
        "get_weekly_volume",
        "Volume per ISO week: strength and cardio sessions and minutes, running and cycling km, "
        "strength tonnage.",
        "calcule ton volume",
        Weeks,
        get_weekly_volume,
    ),
]
