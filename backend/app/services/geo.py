"""Small geometry helpers for the map: bounding boxes and route simplification.

Distances are computed on a flat projection centred on the route
(equirectangular): over a few dozen kilometres the error is far below a
pixel on screen, and it is much simpler than spherical maths.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

Point = tuple[float, float]  # (latitude, longitude) in degrees

EARTH_RADIUS_M = 6_371_000
# Metres per pixel at zoom 0 on the equator, for 256-px OpenStreetMap tiles.
METRES_PER_PIXEL_ZOOM_0 = 156_543.03
# Points closer than this many pixels to the simplified line are dropped:
# invisible on screen, but they make the answer much lighter.
TOLERANCE_PX = 1.5


@dataclass(frozen=True)
class Bounds:
    """A latitude/longitude rectangle (what the map shows, or around a route)."""

    south: float
    west: float
    north: float
    east: float

    def intersects(self, other: "Bounds") -> bool:
        return not (
            other.west > self.east
            or other.east < self.west
            or other.south > self.north
            or other.north < self.south
        )

    def union(self, other: "Bounds") -> "Bounds":
        return Bounds(
            min(self.south, other.south),
            min(self.west, other.west),
            max(self.north, other.north),
            max(self.east, other.east),
        )


def bounds_of(points: Sequence[Point]) -> Bounds:
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    return Bounds(min(lats), min(lngs), max(lats), max(lngs))


def tolerance_for_zoom(zoom: float, latitude: float) -> float:
    """How many metres ``TOLERANCE_PX`` pixels represent at this zoom level.

    Each zoom level halves the size of a pixel; pixels also shrink towards
    the poles (Mercator projection), hence the cosine.
    """
    metres_per_pixel = METRES_PER_PIXEL_ZOOM_0 * math.cos(math.radians(latitude)) / 2**zoom
    return TOLERANCE_PX * metres_per_pixel


def simplify(points: Sequence[Point], tolerance_m: float) -> list[Point]:
    """Douglas-Peucker: keep the fewest points so the line moves less than ``tolerance_m``.

    The algorithm takes the segment from the first to the last point, finds
    the point farthest from it and, if it is farther than the tolerance,
    keeps it and repeats on both halves. A stack replaces recursion, so a
    route of 50,000 points cannot overflow Python's recursion limit.
    """
    if len(points) < 3 or tolerance_m <= 0:
        return list(points)
    xy = _project(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        farthest, distance = _farthest(xy, first, last)
        if distance > tolerance_m:
            keep[farthest] = True
            stack.append((first, farthest))
            stack.append((farthest, last))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def _project(points: Sequence[Point]) -> list[tuple[float, float]]:
    """Latitude/longitude to metres on a plane centred on the first point."""
    lat0 = math.radians(points[0][0])
    scale_x = EARTH_RADIUS_M * math.cos(lat0) * math.pi / 180
    scale_y = EARTH_RADIUS_M * math.pi / 180
    return [(lng * scale_x, lat * scale_y) for lat, lng in points]


def _farthest(xy: list[tuple[float, float]], first: int, last: int) -> tuple[int, float]:
    """Index of the point between ``first`` and ``last`` farthest from their segment."""
    (ax, ay), (bx, by) = xy[first], xy[last]
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    best_index, best_distance = first, 0.0
    for index in range(first + 1, last):
        px, py = xy[index]
        if length_sq == 0:  # loop: start and end are the same point
            distance = math.hypot(px - ax, py - ay)
        else:
            # Projection of the point on the segment, clamped to its ends.
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
            distance = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if distance > best_distance:
            best_index, best_distance = index, distance
    return best_index, best_distance
