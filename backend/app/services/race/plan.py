"""Race-day pacing: kilometre splits with a negative split, hills, and how
realistic a target time is compared with the predicted range."""

from dataclasses import dataclass
from enum import StrEnum

# Negative split (FRANKS's spec: "départ prudent puis négative split"): the first
# half 1 % slower than the average pace, the second half 1 % faster. Same total.
NEGATIVE_SPLIT = 0.01
# Hills: about one minute per 100 m of climbing on a loop course (the descents
# give some of it back). A rough rule, said as such on screen.
SECONDS_PER_METRE_CLIMBED = 0.6


@dataclass(frozen=True)
class Split:
    km: float  # distance at the end of this split (the last one may be partial)
    pace_s_per_km: float
    elapsed_s: float  # time on the clock at this point


@dataclass(frozen=True)
class PacePlan:
    distance_m: float
    target_time_s: float  # including the hill allowance
    average_pace_s_per_km: float
    hill_allowance_s: float
    splits: list[Split]


def hill_allowance(elevation_gain_m: float) -> float:
    return max(elevation_gain_m, 0.0) * SECONDS_PER_METRE_CLIMBED


def pace_plan(distance_m: float, flat_time_s: float, elevation_gain_m: float = 0.0) -> PacePlan:
    """Splits for running ``distance_m`` in ``flat_time_s`` (+ the hill allowance)."""
    if distance_m <= 0 or flat_time_s <= 0:
        raise ValueError("distance and time must be positive")
    extra = hill_allowance(elevation_gain_m)
    total = flat_time_s + extra
    average = total / (distance_m / 1000)
    half = distance_m / 2
    splits: list[Split] = []
    elapsed = 0.0
    done = 0.0
    while done < distance_m - 1e-6:
        step = min(1000.0, distance_m - done)
        middle = done + step / 2  # which half this kilometre mostly belongs to
        pace = average * (1 + NEGATIVE_SPLIT if middle <= half else 1 - NEGATIVE_SPLIT)
        elapsed += pace * step / 1000
        done += step
        splits.append(Split(km=round(done / 1000, 3), pace_s_per_km=pace, elapsed_s=elapsed))
    # Rounding of the halves (odd number of km): put the last split exactly on target.
    if splits:
        last = splits[-1]
        splits[-1] = Split(last.km, last.pace_s_per_km, total)
    return PacePlan(distance_m, total, average, extra, splits)


class Feasibility(StrEnum):
    REALISTIC = "realistic"
    AMBITIOUS = "ambitious"
    UNLIKELY = "unlikely"


@dataclass(frozen=True)
class FeasibilityResult:
    verdict: Feasibility
    gap_s: float  # target minus the predicted time (negative = faster than predicted)
    gap_pct: float


# A target this much faster than the fast end of the range is "unlikely".
UNLIKELY_BEYOND = 0.02


def feasibility(target_s: float, predicted_s: float, fastest_s: float) -> FeasibilityResult:
    """Compare a target time with the prediction and the fast end of its range.

    - at or slower than the prediction: realistic;
    - between the prediction and a little beyond the fast end: ambitious;
    - faster still: unlikely.
    """
    gap = target_s - predicted_s
    if target_s >= predicted_s:
        verdict = Feasibility.REALISTIC
    elif target_s >= fastest_s * (1 - UNLIKELY_BEYOND):
        verdict = Feasibility.AMBITIOUS
    else:
        verdict = Feasibility.UNLIKELY
    return FeasibilityResult(verdict, gap, gap / predicted_s)
