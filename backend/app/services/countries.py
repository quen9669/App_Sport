"""Which country a GPS point is in, without asking any web service.

The borders come from Natural Earth (public domain), stored in
``app/geodata/countries.json.gz``: precise (1:10m, about 100 m) for Europe,
coarser (1:50m) elsewhere. A point is tested against each country's bounding
box first, then with the "ray casting" test on its polygons: draw a line from
the point towards the east and count how many borders it crosses. An odd count
means the point is inside.

Computing it here keeps the activities' positions on the machine: nothing is
sent to a geocoding service.
"""

import gzip
import json
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "geodata" / "countries.json.gz"

Ring = list[tuple[float, float]]  # (longitude, latitude) points, closed loop
Polygon = list[Ring]  # outer border first, then holes (lakes, enclaves)


@dataclass(frozen=True)
class Country:
    code: str  # ISO 3166-1 alpha-2, e.g. "LU"
    polygons: list[Polygon]
    west: float
    south: float
    east: float
    north: float

    def contains(self, lng: float, lat: float) -> bool:
        if not (self.west <= lng <= self.east and self.south <= lat <= self.north):
            return False
        return any(_in_polygon(lng, lat, polygon) for polygon in self.polygons)


@cache
def _countries() -> list[Country]:
    """Read the borders once (about 4 MB of JSON), on the first lookup."""
    data = json.loads(gzip.decompress(DATA_FILE.read_bytes()))
    countries = []
    for item in data["countries"]:
        polygons = [[[(p[0], p[1]) for p in ring] for ring in poly] for poly in item["polygons"]]
        points = [p for poly in polygons for p in poly[0]]
        countries.append(
            Country(
                code=item["code"],
                polygons=polygons,
                west=min(p[0] for p in points),
                south=min(p[1] for p in points),
                east=max(p[0] for p in points),
                north=max(p[1] for p in points),
            )
        )
    return countries


def _in_ring(lng: float, lat: float, ring: Ring) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        (x1, y1), (x2, y2) = previous, current
        # Does this border segment cross the horizontal line through the point,
        # on the east side of the point?
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
        previous = current
    return inside


def _in_polygon(lng: float, lat: float, polygon: Polygon) -> bool:
    outer, *holes = polygon
    return _in_ring(lng, lat, outer) and not any(_in_ring(lng, lat, hole) for hole in holes)


# A start on a beach or a harbour may fall just outside the simplified coastline:
# then the nearest border point within this distance (in degrees, ~3 km) wins.
COAST_TOLERANCE_DEG = 0.03


@lru_cache(maxsize=4096)
def _country_at_rounded(lat: float, lng: float) -> str | None:
    for country in _countries():
        if country.contains(lng, lat):
            return country.code
    return _nearest_coast(lat, lng)


def _nearest_coast(lat: float, lng: float) -> str | None:
    best: tuple[float, str] | None = None
    tol = COAST_TOLERANCE_DEG
    for country in _countries():
        if not (
            country.west - tol <= lng <= country.east + tol
            and country.south - tol <= lat <= country.north + tol
        ):
            continue
        for polygon in country.polygons:
            for x, y in polygon[0]:
                distance = max(abs(x - lng), abs(y - lat))
                if distance <= tol and (best is None or distance < best[0]):
                    best = (distance, country.code)
    return best[1] if best else None


def country_at(lat: float | None, lng: float | None) -> str | None:
    """ISO code of the country at this point, or None (at sea, or no point).

    Points are rounded to about 100 m: the same start (home, the gym) is then
    computed only once, thanks to the cache.
    """
    if lat is None or lng is None:
        return None
    return _country_at_rounded(round(lat, 3), round(lng, 3))
