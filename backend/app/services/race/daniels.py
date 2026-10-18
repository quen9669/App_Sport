"""Jack Daniels' VDOT model (Daniels & Gilbert, "Oxygen Power", 1979).

Two formulas, with the speed ``v`` in metres per minute and the time ``t`` in
minutes:

- oxygen cost of running at speed v (ml/kg/min):
  ``VO2(v) = -4.60 + 0.182258 v + 0.000104 v²``
- share of VO2max that can be sustained for t minutes:
  ``%max(t) = 0.8 + 0.1894393 e^(-0.012778 t) + 0.2989558 e^(-0.1932605 t)``

A race of distance d in time t gives ``VDOT = VO2(d / t) / %max(t)``. Going the
other way (the time a VDOT predicts on a distance) has no closed formula: it is
found by bisection, since a longer time always means a lower VDOT.

The tests check the results against Daniels' published tables.
"""

import math
from dataclasses import dataclass

# Search bounds for race times, in minutes: from a 100 m dash to a slow ultra.
_MIN_T, _MAX_T = 0.1, 24 * 60.0


def oxygen_cost(v: float) -> float:
    """VO2 (ml/kg/min) needed to run at ``v`` metres per minute."""
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def sustainable_fraction(t: float) -> float:
    """Share of VO2max a runner can hold for ``t`` minutes (1.0 = 100 %)."""
    return 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)


def vdot(distance_m: float, time_s: float) -> float:
    """VDOT of a race (or race-like effort) of ``distance_m`` in ``time_s``."""
    if distance_m <= 0 or time_s <= 0:
        raise ValueError("distance and time must be positive")
    t = time_s / 60
    return oxygen_cost(distance_m / t) / sustainable_fraction(t)


def race_time(vdot_value: float, distance_m: float) -> float:
    """Seconds a runner of this VDOT should need for ``distance_m`` (all out)."""
    if vdot_value <= 0 or distance_m <= 0:
        raise ValueError("VDOT and distance must be positive")
    low, high = _MIN_T, _MAX_T  # minutes; vdot() decreases when the time grows
    for _ in range(100):  # 100 halvings: far below a hundredth of a second
        middle = (low + high) / 2
        if vdot(distance_m, middle * 60) > vdot_value:
            low = middle  # too fast for this VDOT: the time must be longer
        else:
            high = middle
    return (low + high) / 2 * 60


def speed_for_oxygen(vo2: float) -> float:
    """Speed (m/min) whose oxygen cost is ``vo2``: the positive root of VO2(v)."""
    a, b, c = 0.000104, 0.182258, -4.60 - vo2
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


@dataclass(frozen=True)
class PaceZone:
    key: str  # "easy", "marathon", "threshold", "interval", "repetition"
    slow_s_per_km: float  # the slow end of the zone (or the only pace)
    fast_s_per_km: float


# Share of VDOT for each training intensity, calibrated on Daniels' tables
# (e.g. VDOT 50: easy 5:08-5:38, threshold 4:15, interval 4:00, repetition 3:41 /km).
EASY_RANGE = (0.62, 0.70)
THRESHOLD = 0.88
INTERVAL = 0.95
REPETITION = 1.05
MARATHON_M = 42_195.0


def _pace_at(vdot_value: float, share: float) -> float:
    """Seconds per km at ``share`` of the VDOT's oxygen consumption."""
    return 60_000 / speed_for_oxygen(vdot_value * share)


def training_paces(vdot_value: float) -> list[PaceZone]:
    """Daniels' five training paces, slowest first, in seconds per km."""
    marathon = race_time(vdot_value, MARATHON_M) / (MARATHON_M / 1000)
    return [
        PaceZone("easy", _pace_at(vdot_value, EASY_RANGE[0]), _pace_at(vdot_value, EASY_RANGE[1])),
        PaceZone("marathon", marathon, marathon),
        PaceZone("threshold", *([_pace_at(vdot_value, THRESHOLD)] * 2)),
        PaceZone("interval", *([_pace_at(vdot_value, INTERVAL)] * 2)),
        PaceZone("repetition", *([_pace_at(vdot_value, REPETITION)] * 2)),
    ]
