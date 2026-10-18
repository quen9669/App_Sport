"""Which runs say something about the current form, and the VDOT they give.

FRANKS runs often but rarely races: a training run taken as a race would
underestimate his form. So each run gives two estimates, and the higher wins:

- **as a race**: the VDOT of its distance and time. A run can only be slower
  than what the runner can do, so this is a floor;
- **from heart rate** (when known): Swain's relation "% of VO2 reserve = % of
  heart-rate reserve" says how hard the run was. With the oxygen cost of its
  pace (daniels.oxygen_cost) it gives the VO2max the run implies:
  ``VO2max = 3.5 + (VO2(pace) - 3.5) / %HRR`` (3.5 = oxygen used at rest).

Recent efforts count more (half the weight every ``HALF_LIFE_DAYS``). The
estimate is the weighted mean of the better half of the efforts (an easy day
without heart rate only says "at least this"), with a range from their spread.
Too few or too old efforts: the result says so instead of guessing.
"""

import math
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.services.race.daniels import oxygen_cost, vdot

# Which runs are used.
LOOKBACK_DAYS = 120
MIN_DISTANCE_M = 3000.0
MAX_GAIN_PER_KM = 15.0  # metres of climbing per km: above, too hilly to compare
MAX_PACE_VARIATION = 0.12  # coefficient of variation of the km paces (intervals, stops)
HRR_RANGE = (0.60, 0.97)  # below: too easy for a reliable estimate; above: race effort
# When it is enough.
MIN_EFFORTS = 3
MAX_NEWEST_AGE_DAYS = 60
# Weights and range.
HALF_LIFE_DAYS = 45.0
MIN_HALF_RANGE = 1.0  # VDOT points: even perfect data is not more precise than that
FEW_EFFORTS = 6  # fewer efforts used than this: the range widens by half a point
STALE_DAYS = 30  # newest effort older than this: the range widens by half a point
RESTING_VO2 = 3.5  # ml/kg/min, oxygen used at rest (one "MET")


class Method(StrEnum):
    RACE = "race"  # distance and time only
    HEART_RATE = "heart_rate"  # pace and heart rate


@dataclass(frozen=True)
class RunEffort:
    activity_id: int
    day: date
    distance_m: float
    time_s: float
    average_hr: float | None = None
    elevation_gain_m: float | None = None
    pace_variation: float | None = None  # from the streams, when known
    segment: bool = False  # the best 5/10 km inside a longer run


@dataclass(frozen=True)
class HeartRate:
    max_hr: float
    resting_hr: float


@dataclass(frozen=True)
class ScoredEffort:
    effort: RunEffort
    vdot: float
    method: Method
    weight: float
    used: bool  # in the better half that makes the estimate


class Status(StrEnum):
    OK = "ok"
    INSUFFICIENT = "insufficient"


@dataclass
class FormEstimate:
    status: Status
    vdot: float | None = None
    low: float | None = None  # pessimistic end of the range
    high: float | None = None
    reason: str | None = None  # why it is insufficient (French, shown as is)
    efforts: list[ScoredEffort] = field(default_factory=list)


def usable(effort: RunEffort, today: date) -> bool:
    """Is this run comparable to a race (long enough, flat enough, steady, recent)?"""
    age = (today - effort.day).days
    if age < 0 or age > LOOKBACK_DAYS or effort.distance_m < MIN_DISTANCE_M:
        return False
    if effort.time_s <= 0:
        return False
    gain = effort.elevation_gain_m or 0.0
    if gain / (effort.distance_m / 1000) > MAX_GAIN_PER_KM:
        return False
    return effort.pace_variation is None or effort.pace_variation <= MAX_PACE_VARIATION


def heart_rate_vdot(effort: RunEffort, hr: HeartRate | None) -> float | None:
    """VO2max implied by the pace and heart rate of a run (None if not reliable)."""
    if hr is None or effort.average_hr is None or hr.max_hr <= hr.resting_hr:
        return None
    reserve = (effort.average_hr - hr.resting_hr) / (hr.max_hr - hr.resting_hr)
    if not HRR_RANGE[0] <= reserve <= HRR_RANGE[1]:
        return None
    speed = effort.distance_m / (effort.time_s / 60)  # metres per minute
    return RESTING_VO2 + (oxygen_cost(speed) - RESTING_VO2) / reserve


def score(effort: RunEffort, hr: HeartRate | None, today: date) -> tuple[float, Method, float]:
    """(VDOT, method, weight) of one usable effort."""
    as_race = vdot(effort.distance_m, effort.time_s)
    from_hr = heart_rate_vdot(effort, hr)
    weight = 0.5 ** ((today - effort.day).days / HALF_LIFE_DAYS)
    if from_hr is not None and from_hr > as_race:
        return from_hr, Method.HEART_RATE, weight
    return as_race, Method.RACE, weight


def best_per_activity(
    efforts: list[RunEffort], hr: HeartRate | None, today: date
) -> list[tuple[RunEffort, float, Method, float]]:
    """Score the usable efforts and keep the best one of each run.

    A run and the best 5 km inside it are the same outing: counting both
    would make one good day look like two.
    """
    best: dict[int, tuple[RunEffort, float, Method, float]] = {}
    for effort in efforts:
        if not usable(effort, today):
            continue
        value, method, weight = score(effort, hr, today)
        current = best.get(effort.activity_id)
        if current is None or value > current[1]:
            best[effort.activity_id] = (effort, value, method, weight)
    # From the best VDOT down.
    return sorted(best.values(), key=lambda item: item[1], reverse=True)


def estimate_form(efforts: list[RunEffort], hr: HeartRate | None, today: date) -> FormEstimate:
    scored = best_per_activity(efforts, hr, today)
    if len(scored) < MIN_EFFORTS:
        return FormEstimate(
            Status.INSUFFICIENT,
            reason=(
                f"Pas assez de sorties exploitables : {len(scored)} sur les {LOOKBACK_DAYS} "
                f"derniers jours, il en faut au moins {MIN_EFFORTS} (3 km minimum, peu de "
                "dénivelé, allure régulière)."
            ),
        )
    newest = min((today - item[0].day).days for item in scored)
    if newest > MAX_NEWEST_AGE_DAYS:
        return FormEstimate(
            Status.INSUFFICIENT,
            reason=f"Ta dernière sortie exploitable date de {newest} jours : trop ancienne.",
        )
    # The better half by weight: from the best VDOT down, until half the total
    # weight is reached (and at least MIN_EFFORTS runs).
    total_weight = sum(item[3] for item in scored)
    count, running = 0, 0.0
    for _, _, _, weight in scored:
        if running >= total_weight / 2 and count >= MIN_EFFORTS:
            break
        count += 1
        running += weight
    used = scored[:count]
    weights = sum(item[3] for item in used)
    centre = sum(item[1] * item[3] for item in used) / weights
    spread = math.sqrt(sum(item[3] * (item[1] - centre) ** 2 for item in used) / weights)
    half = max(MIN_HALF_RANGE, spread)
    if len(used) < FEW_EFFORTS:
        half += 0.5  # few efforts: less sure
    if newest > STALE_DAYS:
        half += 0.5  # nothing in the last month: the form may have changed
    return FormEstimate(
        Status.OK,
        vdot=centre,
        low=centre - half,
        high=centre + half,
        efforts=[
            ScoredEffort(effort, value, method, weight, used=rank < count)
            for rank, (effort, value, method, weight) in enumerate(scored)
        ],
    )


# --- Helpers on the streams of one run ------------------------------------------


def best_segment(time_s: list[float], distance_m: list[float], length_m: float) -> float | None:
    """Fastest time to cover ``length_m`` inside a run (two pointers over the samples).

    ``time_s`` and ``distance_m`` are aligned samples (seconds and metres since
    the start). None when the run is shorter than ``length_m``.
    """
    best: float | None = None
    start = 0
    for end in range(len(distance_m)):
        # Move the start forward while the window stays at least length_m long.
        while start + 1 <= end and distance_m[end] - distance_m[start + 1] >= length_m:
            start += 1
        covered = distance_m[end] - distance_m[start]
        if covered >= length_m:
            # Scale to exactly length_m (the window is a few metres longer).
            elapsed = (time_s[end] - time_s[start]) * length_m / covered
            best = elapsed if best is None else min(best, elapsed)
    return best


def pace_variation(time_s: list[float], distance_m: list[float]) -> float | None:
    """Coefficient of variation of the paces of each full kilometre (None if < 3 km).

    Steady runs are around 0.03-0.06; intervals or long stops go well above 0.12.
    """
    if not time_s:
        return None
    paces: list[float] = []
    mark = (distance_m[0] // 1000 + 1) * 1000  # the next full kilometre
    mark_time = time_s[0]  # streams do not always start at 0 s
    for t, d in zip(time_s, distance_m, strict=False):
        if d >= mark:
            paces.append(t - mark_time)
            mark_time = t
            mark += 1000.0
    if len(paces) < 3:
        return None
    mean = sum(paces) / len(paces)
    deviation = math.sqrt(sum((p - mean) ** 2 for p in paces) / len(paces))
    return deviation / mean
