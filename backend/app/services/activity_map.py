"""Routes for the map screen and the series of the activity detail screen.

Map: every activity with a GPS route, filtered by sport, period and distance.
The server only sends what the map shows (the visible rectangle) and
simplifies each route for the zoom level, so even hundreds of activities stay
light for a phone. Activities without GPS (gym sessions) are grouped on their
place (app/services/places.py), so they show on the map and the heatmap too.

Detail: the time series of one activity (altitude, speed, heart rate, GPS),
aligned on the same samples and thinned out to at most ``MAX_DETAIL_POINTS``
so the charts stay smooth.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.repositories import activities as activities_repo
from app.services import geo, polyline
from app.services.classification import RIDE_SPORTS, RUN_SPORTS, Category, effective_category
from app.services.places import PlaceBook
from app.services.stream_codec import decode_streams

# A chart is ~350 px wide on a phone: more points than this are invisible.
MAX_DETAIL_POINTS = 1000
# Without a zoom level, simplify as for a city-wide view.
DEFAULT_ZOOM = 12
# Speed computed from the distance series over this many samples on each
# side, to smooth GPS jitter when the source gives no speed series.
SPEED_WINDOW = 5


class SportGroup(StrEnum):
    RUN = "run"
    RIDE = "ride"
    STRENGTH = "strength"  # weight training and gym classes
    OTHER = "other"  # walks, hikes, swims...


def sport_group(activity: Activity) -> SportGroup:
    if activity.sport_type in RUN_SPORTS:
        return SportGroup.RUN
    if activity.sport_type in RIDE_SPORTS:
        return SportGroup.RIDE
    if effective_category(activity) == Category.STRENGTH:
        return SportGroup.STRENGTH
    return SportGroup.OTHER


@dataclass
class MapFilters:
    sport: SportGroup | None = None  # None = every sport
    since: datetime | None = None  # None = all the history
    min_km: float | None = None
    max_km: float | None = None


@dataclass
class MapRoute:
    activity: Activity
    polyline: str  # simplified for the requested zoom


@dataclass
class MapPlace:
    place: Place
    activities: list[Activity] = field(default_factory=list)  # newest first


@dataclass
class MapResult:
    routes: list[MapRoute] = field(default_factory=list)
    places: list[MapPlace] = field(default_factory=list)  # activities without GPS
    # Rectangle around every matching route, visible or not: the map uses it
    # to frame all the activities when it opens or when a filter changes.
    bounds: geo.Bounds | None = None
    total: int = 0  # matching activities, visible or not


def _matching_activities(db: Session, filters: MapFilters) -> list[Activity]:
    query = select(Activity).where(
        Activity.hidden.is_(False),
        activities_repo.not_duplicate(),
    )
    if filters.since is not None:
        query = query.where(Activity.start_time >= filters.since)
    if filters.min_km is not None:
        query = query.where(Activity.distance_m >= filters.min_km * 1000)
    if filters.max_km is not None:
        query = query.where(Activity.distance_m <= filters.max_km * 1000)
    activities = db.scalars(query.order_by(Activity.start_time)).all()
    # The sport groups are Python sets (classification.py), simpler to filter here.
    if filters.sport is not None:
        return [a for a in activities if sport_group(a) == filters.sport]
    return list(activities)


def map_routes(
    db: Session, filters: MapFilters, visible: geo.Bounds | None, zoom: float | None
) -> MapResult:
    """Matching routes inside ``visible`` (all if None), simplified for ``zoom``,
    and the places of the matching activities without GPS."""
    result = MapResult()
    book = PlaceBook(db)
    by_place: dict[int, MapPlace] = {}
    for activity in _matching_activities(db, filters):
        points = polyline.decode(activity.summary_polyline or "")
        if len(points) < 2:
            _add_to_place(result, by_place, book, activity, visible)
            continue
        box = geo.bounds_of(points)
        result.total += 1
        result.bounds = box if result.bounds is None else result.bounds.union(box)
        if visible is not None and not visible.intersects(box):
            continue  # off screen: not sent
        tolerance = geo.tolerance_for_zoom(zoom or DEFAULT_ZOOM, points[0][0])
        result.routes.append(MapRoute(activity, polyline.encode(geo.simplify(points, tolerance))))
    for item in result.places:
        item.activities.reverse()  # newest first, for the popup
    return result


def _add_to_place(
    result: MapResult,
    by_place: dict[int, MapPlace],
    book: PlaceBook,
    activity: Activity,
    visible: geo.Bounds | None,
) -> None:
    """Count an activity without GPS on its place (if it has one)."""
    place, _ = book.locate(activity)
    if place is None:
        return  # no default place configured: it cannot be shown
    point = (place.latitude, place.longitude)
    box = geo.bounds_of([point])
    result.total += 1
    result.bounds = box if result.bounds is None else result.bounds.union(box)
    if visible is not None and not visible.intersects(box):
        return
    if place.id not in by_place:
        by_place[place.id] = MapPlace(place)
        result.places.append(by_place[place.id])
    by_place[place.id].activities.append(activity)


@dataclass
class DetailSeries:
    """Aligned series: index ``i`` of each list is the same moment."""

    time_s: list[int] = field(default_factory=list)
    distance_m: list[float | None] = field(default_factory=list)
    altitude_m: list[float | None] = field(default_factory=list)
    heartrate: list[float | None] = field(default_factory=list)
    speed_mps: list[float | None] = field(default_factory=list)
    latlng: list[list[float] | None] = field(default_factory=list)


def activity_series(activity: Activity) -> DetailSeries:
    """The activity's streams, aligned and thinned out (empty without streams)."""
    if activity.stream is None:
        return DetailSeries()
    streams = decode_streams(activity.stream.data)
    time = streams.get("time") or []
    if not time:
        return DetailSeries()
    speed = streams.get("velocity_smooth") or _speed_from_distance(
        time, streams.get("distance") or []
    )
    indexes = _evenly_spaced(len(time), MAX_DETAIL_POINTS)
    return DetailSeries(
        time_s=[int(time[i]) for i in indexes],
        distance_m=_pick(streams.get("distance"), indexes),
        altitude_m=_pick(streams.get("altitude"), indexes),
        heartrate=_pick(streams.get("heartrate"), indexes),
        speed_mps=_pick(speed, indexes),
        latlng=_pick(streams.get("latlng"), indexes),
    )


def detail_route(series: DetailSeries, activity: Activity) -> str | None:
    """Route for the detail map: the detailed GPS points, else the summary line."""
    points = [(p[0], p[1]) for p in series.latlng if p is not None]
    if len(points) >= 2:
        return polyline.encode(points)
    return activity.summary_polyline


def _evenly_spaced(length: int, maximum: int) -> list[int]:
    """At most ``maximum`` indexes spread over ``range(length)``, first and last included."""
    if length <= maximum:
        return list(range(length))
    step = (length - 1) / (maximum - 1)
    return [round(i * step) for i in range(maximum)]


def _pick(series: list[Any] | None, indexes: list[int]) -> list[Any]:
    """Values of ``series`` at ``indexes``; None where the series is missing or too short."""
    if not series:
        return [None] * len(indexes)
    return [series[i] if i < len(series) else None for i in indexes]


def _speed_from_distance(time: list[Any], distance: list[Any]) -> list[float | None]:
    """Speed (m/s) from the distance series, averaged over a small window."""
    if len(distance) != len(time):
        return []
    speeds: list[float | None] = []
    for i in range(len(time)):
        low, high = max(0, i - SPEED_WINDOW), min(len(time) - 1, i + SPEED_WINDOW)
        seconds = time[high] - time[low]
        if seconds <= 0 or distance[high] is None or distance[low] is None:
            speeds.append(None)
        else:
            speeds.append(round((distance[high] - distance[low]) / seconds, 2))
    return speeds
