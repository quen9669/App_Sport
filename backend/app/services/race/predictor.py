"""Everything the "Course" screen shows, read from the database.

The other modules of this package are pure calculations; this one finds the
runs, turns them into ``RunEffort`` objects and puts the results together:
current form, predicted times, training paces and the plan for the target race.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import Activity, RaceTarget
from app.repositories import activities as activities_repo
from app.repositories import race as race_repo
from app.services.classification import RUN_SPORTS
from app.services.race import daniels, plan, riegel
from app.services.race.efforts import (
    LOOKBACK_DAYS,
    FormEstimate,
    HeartRate,
    RunEffort,
    Status,
    best_segment,
    estimate_form,
    pace_variation,
)
from app.services.stream_codec import decode_streams
from app.services.training_load import heart_rate_params
from app.services.weeks import local_today

# The distances shown on screen, with their French labels.
STANDARD_DISTANCES = [
    ("5 km", 5000.0),
    ("10 km", 10_000.0),
    ("Semi-marathon", 21_097.5),
    ("Marathon", 42_195.0),
]
# Best efforts searched inside longer runs (only when the run is at least 1 km longer).
SEGMENT_LENGTHS = (5000.0, 10_000.0)


@dataclass(frozen=True)
class Prediction:
    label: str
    distance_m: float
    time_s: float  # from the central VDOT
    fastest_s: float  # from the high end of the range
    slowest_s: float
    riegel_s: float  # second opinion: Riegel from the predicted 5 km


@dataclass(frozen=True)
class TargetReport:
    target: RaceTarget
    days_left: int
    predicted_s: float | None  # None while the form is unknown
    required_vdot: float | None  # the VDOT the target time needs
    pace_plan: plan.PacePlan | None
    feasibility: plan.FeasibilityResult | None


@dataclass(frozen=True)
class RaceReport:
    form: FormEstimate
    runs: dict[int, Activity]  # activity id -> run, for the list of efforts (name, heart rate)
    excluded: list[Activity]
    predictions: list[Prediction]
    zones: list[daniels.PaceZone]
    target: TargetReport | None


def _run_window(db: Session, today: date, timezone: str) -> list[Activity]:
    """Runs of the last LOOKBACK_DAYS (local days), oldest first, duplicates skipped."""
    zone = ZoneInfo(timezone)
    start = datetime.combine(today - timedelta(days=LOOKBACK_DAYS), time(), tzinfo=zone)
    end = datetime.combine(today + timedelta(days=1), time(), tzinfo=zone)
    return [
        activity
        for activity in activities_repo.activities_between(
            db, start.astimezone(UTC), end.astimezone(UTC)
        )
        if activity.sport_type in RUN_SPORTS and not activity.hidden
    ]


def _comparable(activity: Activity) -> bool:
    # Treadmill distances come from a foot pod or a guess: not reliable enough.
    return bool(activity.distance_m) and not activity.is_trainer


def _time_and_distance(activity: Activity) -> tuple[list[float], list[float]]:
    """Aligned (time, distance) samples of the run, without gaps; empty without streams."""
    if activity.stream is None:
        return [], []
    streams = decode_streams(activity.stream.data)
    pairs = [
        (float(t), float(d))
        for t, d in zip(streams.get("time") or [], streams.get("distance") or [], strict=False)
        if t is not None and d is not None
    ]
    return [t for t, _ in pairs], [d for _, d in pairs]


def efforts_of(activity: Activity, timezone: str) -> list[RunEffort]:
    """The whole run, plus its best 5 km / 10 km when the streams allow it."""
    assert activity.distance_m is not None  # checked by _comparable
    day = activity.start_time.astimezone(ZoneInfo(timezone)).date()
    times, distances = _time_and_distance(activity)
    whole = RunEffort(
        activity_id=activity.id,
        day=day,
        distance_m=activity.distance_m,
        # Moving time: a stop at a red light says nothing about the form.
        time_s=float(activity.moving_time_s or activity.elapsed_time_s),
        average_hr=activity.average_heartrate,
        elevation_gain_m=activity.elevation_gain_m,
        pace_variation=pace_variation(times, distances) if times else None,
    )
    efforts = [whole]
    for length in SEGMENT_LENGTHS:
        if activity.distance_m < length + 1000 or not times:
            continue
        segment_time = best_segment(times, distances, length)
        if segment_time is None:
            continue
        share = length / activity.distance_m
        efforts.append(
            RunEffort(
                activity_id=activity.id,
                day=day,
                distance_m=length,
                time_s=segment_time,
                # The run's average heart rate is not the segment's: leave it out.
                elevation_gain_m=(activity.elevation_gain_m or 0.0) * share,
                segment=True,
            )
        )
    return efforts


def _heart_rate(db: Session, today: date) -> HeartRate | None:
    params = heart_rate_params(db, today)
    if not params.usable:
        return None
    assert params.max_hr is not None and params.resting_hr is not None  # for mypy
    return HeartRate(params.max_hr, params.resting_hr)


def predictions_for(form: FormEstimate) -> list[Prediction]:
    if form.status is not Status.OK:
        return []
    assert form.vdot is not None and form.low is not None and form.high is not None
    five_k = daniels.race_time(form.vdot, 5000.0)
    return [
        Prediction(
            label=label,
            distance_m=distance,
            time_s=daniels.race_time(form.vdot, distance),
            fastest_s=daniels.race_time(form.high, distance),
            slowest_s=daniels.race_time(form.low, distance),
            riegel_s=riegel.riegel_time(5000.0, five_k, distance),
        )
        for label, distance in STANDARD_DISTANCES
    ]


def target_report(target: RaceTarget, form: FormEstimate, today: date) -> TargetReport:
    """Plan and feasibility of the target race, against the current form."""
    predicted = fastest = None
    if form.status is Status.OK:
        assert form.vdot is not None and form.high is not None
        predicted = daniels.race_time(form.vdot, target.distance_m)
        fastest = daniels.race_time(form.high, target.distance_m)
    # Plan on the target time when there is one (it is what FRANKS will try to
    # run), else on the predicted time. The target is for race day, hills
    # included, so the flat time is the target minus the hill allowance.
    pacing = None
    if target.target_time_s is not None:
        flat = target.target_time_s - plan.hill_allowance(target.elevation_gain_m)
        if flat > 0:
            pacing = plan.pace_plan(target.distance_m, flat, target.elevation_gain_m)
    elif predicted is not None:
        pacing = plan.pace_plan(target.distance_m, predicted, target.elevation_gain_m)
    verdict = required = None
    if target.target_time_s is not None:
        flat_target = target.target_time_s - plan.hill_allowance(target.elevation_gain_m)
        if flat_target > 0:
            required = daniels.vdot(target.distance_m, flat_target)
            if predicted is not None and fastest is not None:
                verdict = plan.feasibility(flat_target, predicted, fastest)
    return TargetReport(
        target=target,
        days_left=(target.race_date - today).days,
        predicted_s=predicted,
        required_vdot=required,
        pace_plan=pacing,
        feasibility=verdict,
    )


def race_report(db: Session, timezone: str, now: datetime | None = None) -> RaceReport:
    today = local_today(timezone, now)
    runs = [run for run in _run_window(db, today, timezone) if _comparable(run)]
    kept = [run for run in runs if not run.excluded_from_race]
    efforts = [effort for run in kept for effort in efforts_of(run, timezone)]
    form = estimate_form(efforts, _heart_rate(db, today), today)
    zones = daniels.training_paces(form.vdot) if form.vdot is not None else []
    target = race_repo.get_target(db)
    return RaceReport(
        form=form,
        runs={run.id: run for run in kept},
        excluded=[run for run in runs if run.excluded_from_race],
        predictions=predictions_for(form),
        zones=zones,
        target=target_report(target, form, today) if target is not None else None,
    )
