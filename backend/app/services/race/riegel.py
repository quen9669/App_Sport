"""Riegel's formula (Peter Riegel, 1977): ``T2 = T1 × (D2 / D1) ^ exponent``.

A known time T1 on distance D1 gives a time T2 on D2. The exponent says how
much a runner slows down when the distance grows: 1.06 by default (Riegel's
value), higher for runners with less endurance. Used as a second opinion next
to the VDOT model, which is more accurate between 1.5 km and the marathon.
"""

DEFAULT_EXPONENT = 1.06


def riegel_time(
    known_distance_m: float,
    known_time_s: float,
    target_distance_m: float,
    exponent: float = DEFAULT_EXPONENT,
) -> float:
    if min(known_distance_m, known_time_s, target_distance_m) <= 0:
        raise ValueError("distances and time must be positive")
    return float(known_time_s * (target_distance_m / known_distance_m) ** exponent)
