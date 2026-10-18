"""Tools about recovery: sleep, resting heart rate and HRV, training load."""

import statistics
from datetime import timedelta
from typing import Any

from app.coach.tools.base import Days, Tool, ToolContext, Weeks, rounded
from app.services.health_dashboard import HealthDay, health_days, sleep_regularity
from app.services.training_load import training_load
from app.services.weeks import current_week

# Averages over the last week compared with the whole period (the "baseline").
RECENT_DAYS = 7


def _clock(minutes: int | None) -> str | None:
    """Minutes from midnight (negative = evening before) to "23:30"."""
    if minutes is None:
        return None
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 1) if values else None


def _days(ctx: ToolContext, days: int) -> list[HealthDay]:
    start = ctx.today - timedelta(days=days - 1)
    return health_days(ctx.db, start, ctx.today, ctx.timezone)


def get_sleep(ctx: ToolContext, args: Days) -> dict[str, Any]:
    days = [d for d in _days(ctx, args.days) if d.sleep_s is not None]
    hours = [d.sleep_s / 3600 for d in days if d.sleep_s is not None]
    recent = [d.sleep_s / 3600 for d in days[-RECENT_DAYS:] if d.sleep_s is not None]
    regularity = sleep_regularity(days)
    return {
        "period_days": args.days,
        "nights_recorded": len(days),
        "average_hours": _mean(hours),
        "average_hours_last_7_nights": _mean(recent),
        "bedtime_spread_min": regularity.bedtime_sd_min,  # standard deviation: low = regular
        "wake_spread_min": regularity.wake_sd_min,
        "nights": [
            {
                "night_of": d.day.isoformat(),
                "hours": rounded(d.sleep_s / 3600 if d.sleep_s else None),
                "score": d.sleep_score,
                "bedtime": _clock(d.bedtime_min),
                "wake": _clock(d.wake_min),
            }
            for d in days[-60:]
        ],
    }


def get_recovery_metrics(ctx: ToolContext, args: Days) -> dict[str, Any]:
    days = _days(ctx, args.days)
    rhr = [float(d.resting_hr) for d in days if d.resting_hr is not None]
    hrv = [d.hrv_ms for d in days if d.hrv_ms is not None]
    recent = days[-RECENT_DAYS:]
    return {
        "period_days": args.days,
        "resting_hr": {
            "days_recorded": len(rhr),
            "average": _mean(rhr),
            "average_last_7_days": _mean([float(d.resting_hr) for d in recent if d.resting_hr]),
        },
        "hrv_ms": {
            "days_recorded": len(hrv),
            "average": _mean(hrv),
            "average_last_7_days": _mean([d.hrv_ms for d in recent if d.hrv_ms is not None]),
        },
        "days": [
            {"date": d.day.isoformat(), "resting_hr": d.resting_hr, "hrv_ms": rounded(d.hrv_ms)}
            for d in days[-60:]
            if d.resting_hr is not None or d.hrv_ms is not None
        ],
        "note": "A resting HR clearly above its baseline or an HRV clearly below it over "
        "several days can mean fatigue; one day alone means little.",
    }


def get_training_load(ctx: ToolContext, args: Weeks) -> dict[str, Any]:
    last = current_week(ctx.timezone, ctx.now)
    summary = training_load(ctx.db, last, args.weeks, ctx.timezone, ctx.now)
    return {
        "method": "Banister TRIMP from heart rate when available, else minutes x effort",
        "weeks": [
            {
                "week": item.week.label,
                "load": round(item.load),
                "sessions": item.sessions,
                "with_heart_rate": item.with_heart_rate,
            }
            for item in summary.weeks
        ],
        "acute_last_7_days": round(summary.acute),
        "chronic_weekly_average_4_weeks": round(summary.chronic),
        "acute_chronic_ratio": summary.acwr,  # None while history is too short
        "note": "Ratio 0.8-1.3 is the usual comfortable zone; above 1.5 the load rose fast.",
    }


TOOLS = [
    Tool(
        "get_sleep",
        "Sleep of the last N nights (Garmin): duration, score, bed and wake times, averages and "
        "regularity.",
        "lit ton sommeil",
        Days,
        get_sleep,
    ),
    Tool(
        "get_recovery_metrics",
        "Resting heart rate and HRV of the last N days, with the last-7-days average against "
        "the period average.",
        "lit ta récupération",
        Days,
        get_recovery_metrics,
    ),
    Tool(
        "get_training_load",
        "Training load per ISO week, last 7 days against the 4 weeks before (acute:chronic ratio).",
        "calcule ta charge",
        Weeks,
        get_training_load,
    ),
]
