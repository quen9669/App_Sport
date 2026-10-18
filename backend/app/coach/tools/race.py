"""Tools about running races: the predictor of phase 4, read as it is (no recomputing)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.coach.tools.base import NoInput, Tool, ToolContext, rounded
from app.services.race import daniels
from app.services.race.predictor import race_report


def _clock(seconds: float) -> str:
    total = round(seconds)
    h, m, s = total // 3600, total % 3600 // 60, total % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _pace(seconds_per_km: float) -> str:
    return f"{_clock(seconds_per_km)} /km"


class DistanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distance_km: float | None = Field(
        default=None,
        ge=0.8,
        le=100,
        description="A race distance in km; empty = 5 km, 10 km, half and marathon.",
    )


def get_race_predictions(ctx: ToolContext, args: DistanceInput) -> dict[str, Any]:
    report = race_report(ctx.db, ctx.timezone, ctx.now)
    form = report.form
    result: dict[str, Any] = {
        "form_status": form.status,
        "reason_if_insufficient": form.reason,
        "vdot": rounded(form.vdot),
        "vdot_range": [rounded(form.low), rounded(form.high)] if form.vdot else None,
        "efforts_used": sum(1 for e in form.efforts if e.used),
        "efforts_from_heart_rate": sum(1 for e in form.efforts if e.method == "heart_rate"),
    }
    if form.vdot is not None and form.low is not None and form.high is not None:
        if args.distance_km is not None:
            metres = args.distance_km * 1000
            result["prediction"] = {
                "distance_km": args.distance_km,
                "time": _clock(daniels.race_time(form.vdot, metres)),
                "range": [
                    _clock(daniels.race_time(form.high, metres)),
                    _clock(daniels.race_time(form.low, metres)),
                ],
            }
        else:
            result["predictions"] = [
                {
                    "distance": p.label,
                    "time": _clock(p.time_s),
                    "range": [_clock(p.fastest_s), _clock(p.slowest_s)],
                    "riegel": _clock(p.riegel_s),
                }
                for p in report.predictions
            ]
    target = report.target
    if target is not None:
        result["target_race"] = {
            "name": target.target.name,
            "distance_km": target.target.distance_m / 1000,
            "date": target.target.race_date.isoformat(),
            "days_left": target.days_left,
            "target_time": _clock(target.target.target_time_s)
            if target.target.target_time_s
            else None,
            "elevation_gain_m": target.target.elevation_gain_m,
            "predicted_time": _clock(target.predicted_s) if target.predicted_s else None,
            "required_vdot": rounded(target.required_vdot),
            "feasibility": target.feasibility.verdict if target.feasibility else None,
            "average_pace_planned": _pace(target.pace_plan.average_pace_s_per_km)
            if target.pace_plan
            else None,
        }
    return result


def get_pace_zones(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    report = race_report(ctx.db, ctx.timezone, ctx.now)
    if not report.zones:
        return {"error": "form unknown (not enough recent runs): no pace zones"}
    return {
        "vdot": rounded(report.form.vdot),
        "zones": [
            {
                "zone": zone.key,
                "pace": _pace(zone.fast_s_per_km)
                if zone.slow_s_per_km == zone.fast_s_per_km
                else f"{_pace(zone.slow_s_per_km)} to {_pace(zone.fast_s_per_km)}",
            }
            for zone in report.zones
        ],
        "source": "Jack Daniels' VDOT tables",
    }


TOOLS = [
    Tool(
        "get_race_predictions",
        "Current running form (VDOT with its range), predicted race times, and FRANKS's target "
        "race with its feasibility. Computed by the app: quote, do not recompute.",
        "regarde tes prédictions de course",
        DistanceInput,
        get_race_predictions,
    ),
    Tool(
        "get_pace_zones",
        "Training paces (easy, marathon, threshold, interval, repetition) from the current VDOT.",
        "lit tes allures",
        NoInput,
        get_pace_zones,
    ),
]
