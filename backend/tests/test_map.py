"""Map routes (filters, visible area, simplification) and the activity detail."""

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.db.models.enums import DataSource
from app.repositories import activities as activities_repo
from app.services import geo, polyline
from app.services.activity_map import MapFilters, SportGroup, activity_series, map_routes
from app.services.stream_codec import encode_streams, point_count

LUXEMBOURG = (49.61, 6.13)
TRIER = (49.75, 6.64)


def loop(center: tuple[float, float], points: int = 200, radius_deg: float = 0.02) -> list[Any]:
    """A circle of ``points`` points around ``center`` (a few km wide)."""
    lat, lng = center
    return [
        (
            round(lat + radius_deg * math.sin(2 * math.pi * i / points), 6),
            round(lng + radius_deg * math.cos(2 * math.pi * i / points), 6),
        )
        for i in range(points)
    ]


def add(
    db: Session,
    external_id: str,
    sport_type: str = "running",
    days_ago: int = 1,
    km: float = 10,
    route: list[Any] | None = None,
    **fields: Any,
) -> Activity:
    values: dict[str, Any] = {
        "name": f"{sport_type} {external_id}",
        "sport_type": sport_type,
        "start_time": datetime.now(UTC) - timedelta(days=days_ago),
        "elapsed_time_s": 3600,
        "distance_m": km * 1000,
        "summary_polyline": polyline.encode(route if route is not None else loop(LUXEMBOURG)),
    }
    values.update(fields)
    activity, _ = activities_repo.upsert_activity(db, DataSource.GARMIN, external_id, values)
    db.commit()
    return activity


# --- Geometry ------------------------------------------------------------------


def test_simplify_drops_points_on_a_straight_line() -> None:
    line = [(49.6 + i / 10_000, 6.1) for i in range(100)]  # ~1 km, perfectly straight
    assert geo.simplify(line, tolerance_m=1) == [line[0], line[-1]]


def test_simplify_keeps_corners_and_more_points_when_zoomed_in() -> None:
    route = loop(LUXEMBOURG, points=500)
    far = geo.simplify(route, geo.tolerance_for_zoom(10, LUXEMBOURG[0]))
    close = geo.simplify(route, geo.tolerance_for_zoom(16, LUXEMBOURG[0]))
    assert 3 <= len(far) < len(close) <= len(route)
    assert far[0] == route[0] and far[-1] == route[-1]


def test_bounds_intersection() -> None:
    city = geo.bounds_of(loop(LUXEMBOURG))
    assert city.intersects(geo.bounds_of(loop(LUXEMBOURG, radius_deg=0.01)))
    assert not city.intersects(geo.bounds_of(loop(TRIER)))


# --- Map routes -------------------------------------------------------------------


def test_filters_by_sport_period_and_distance(db: Session) -> None:
    run = add(db, "1", "running", days_ago=3, km=10)
    add(db, "2", "Ride", days_ago=3, km=60)
    add(db, "3", "running", days_ago=100, km=21)
    add(db, "4", "hiking", days_ago=3, km=8)

    def ids(**kwargs: Any) -> list[int]:
        result = map_routes(db, MapFilters(**kwargs), None, 12)
        return [item.activity.id for item in result.routes]

    assert len(ids()) == 4
    assert ids(sport=SportGroup.RUN, since=datetime.now(UTC) - timedelta(days=30)) == [run.id]
    assert len(ids(min_km=15)) == 2
    assert len(ids(sport=SportGroup.WALK)) == 1  # the hike
    assert ids(sport=SportGroup.OTHER) == []


def test_hidden_duplicates_and_indoor_sessions_are_not_on_the_map(db: Session) -> None:
    add(db, "1")
    add(db, "2", hidden=True)
    add(db, "3", duplicate_status="confirmed")
    add(db, "4", "strength_training", summary_polyline=None)
    assert len(map_routes(db, MapFilters(), None, 12).routes) == 1


def test_only_visible_routes_are_sent_but_bounds_cover_all(db: Session) -> None:
    add(db, "1", route=loop(LUXEMBOURG))
    add(db, "2", route=loop(TRIER))
    around_luxembourg = geo.Bounds(south=49.5, west=6.0, north=49.7, east=6.3)

    result = map_routes(db, MapFilters(), around_luxembourg, 13)

    assert len(result.routes) == 1
    assert result.total == 2
    assert result.bounds is not None and result.bounds.east > 6.6  # Trier included


def test_routes_endpoint(client: TestClient, db: Session) -> None:
    add(db, "1", "running", route=loop(LUXEMBOURG, points=400))
    add(db, "2", "Ride", km=50)

    body = client.get("/api/map/routes", params={"sport": "run", "zoom": 11}).json()

    assert body["total"] == 1
    route = body["routes"][0]
    assert route["sport"] == "run"
    assert 3 <= len(polyline.decode(route["polyline"])) < 400  # simplified
    bad = client.get("/api/map/routes", params={"bbox": "not,a,box"})
    assert bad.status_code == 422


# --- Activity detail ----------------------------------------------------------------


def with_streams(db: Session, activity: Activity, streams: dict[str, list[Any]]) -> None:
    activities_repo.save_stream(
        db, activity, list(streams), point_count(streams), encode_streams(streams)
    )
    db.commit()


def test_series_are_aligned_thinned_and_get_a_speed(db: Session) -> None:
    activity = add(db, "1")
    samples = 3000
    with_streams(
        db,
        activity,
        {
            "time": list(range(samples)),
            "distance": [i * 3.0 for i in range(samples)],  # 3 m/s
            "heartrate": [140] * samples,
            "latlng": [[49.6, 6.1 + i / 100_000] for i in range(samples)],
        },
    )

    series = activity_series(activity)

    assert len(series.time_s) == 1000
    assert series.time_s[0] == 0 and series.time_s[-1] == samples - 1
    assert len(series.latlng) == len(series.heartrate) == len(series.altitude_m) == 1000
    assert series.altitude_m[0] is None  # no altitude series: None, still aligned
    assert series.speed_mps[500] == 3.0  # computed from the distance


def test_detail_endpoint(client: TestClient, db: Session) -> None:
    activity = add(db, "1", average_heartrate=150.0)
    with_streams(db, activity, {"time": [0, 10, 20], "altitude": [300.0, 305.0, 302.0]})

    body = client.get(f"/api/activities/{activity.id}").json()

    assert body["sport"] == "run" and body["category"] == "cardio"
    assert body["series"]["altitude_m"] == [300.0, 305.0, 302.0]
    assert body["polyline"]  # no GPS stream: the summary route is used
    indoor = add(db, "2", "strength_training", summary_polyline=None)
    empty = client.get(f"/api/activities/{indoor.id}").json()
    assert empty["polyline"] is None and empty["series"]["time_s"] == []
    assert client.get("/api/activities/9999").status_code == 404


# --- Places of activities without GPS ---------------------------------------------


def gyms(db: Session) -> tuple[Place, Place]:
    gare = Place(name="Jims Gare", latitude=49.6004, longitude=6.1319, role="strength_default")
    gasperich = Place(
        name="Jims Gasperich", latitude=49.5875, longitude=6.1208, role="other_default"
    )
    db.add_all([gare, gasperich])
    db.commit()
    return gare, gasperich


def test_activities_without_gps_go_to_the_default_place_of_their_kind(db: Session) -> None:
    gare, gasperich = gyms(db)
    add(db, "1", "strength_training", summary_polyline=None)
    add(db, "2", "strength_training", summary_polyline=None)
    add(db, "3", "indoor_cycling", summary_polyline=None)
    add(db, "4", "running")  # has a route: not on a place

    result = map_routes(db, MapFilters(), None, 12)

    counts = {item.place.id: len(item.activities) for item in result.places}
    assert counts == {gare.id: 2, gasperich.id: 1}
    assert result.total == 4
    strength_only = map_routes(db, MapFilters(sport=SportGroup.STRENGTH), None, 12)
    assert [item.place.id for item in strength_only.places] == [gare.id]
    assert strength_only.routes == []


def test_a_place_chosen_by_hand_wins_and_can_be_reset(client: TestClient, db: Session) -> None:
    gare, gasperich = gyms(db)
    session = add(db, "1", "strength_training", summary_polyline=None)

    detail = client.get(f"/api/activities/{session.id}").json()
    assert detail["place"]["id"] == gare.id and detail["place"]["chosen"] is False

    moved = client.patch(f"/api/activities/{session.id}/place", json={"place_id": gasperich.id})
    assert moved.json()["place"] == {
        "id": gasperich.id,
        "name": "Jims Gasperich",
        "latitude": 49.5875,
        "longitude": 6.1208,
        "chosen": True,
    }
    reset = client.patch(f"/api/activities/{session.id}/place", json={"place_id": None})
    assert reset.json()["place"]["id"] == gare.id
    missing = client.patch(f"/api/activities/{session.id}/place", json={"place_id": 999})
    assert missing.status_code == 404


def test_places_crud_and_default_roles(client: TestClient, db: Session) -> None:
    gare, _ = gyms(db)
    created = client.post(
        "/api/places",
        json={
            "name": "Jims Kirchberg",
            "latitude": 49.63,
            "longitude": 6.16,
            "role": "strength_default",
        },
    )
    assert created.status_code == 201
    new_id = created.json()["id"]
    # The role moved: Jims Gare is no longer the strength default.
    roles = {p["name"]: p["role"] for p in client.get("/api/places").json()}
    assert roles == {
        "Jims Gare": None,
        "Jims Gasperich": "other_default",
        "Jims Kirchberg": "strength_default",
    }

    renamed = client.patch(f"/api/places/{gare.id}", json={"name": "Jims Gare (Junck)"})
    assert renamed.json()["name"] == "Jims Gare (Junck)" and renamed.json()["role"] is None
    bad = client.post("/api/places", json={"name": "x", "latitude": 95, "longitude": 6})
    assert bad.status_code == 422

    session = add(db, "1", "strength_training", summary_polyline=None, place_id=new_id)
    assert client.delete(f"/api/places/{new_id}").status_code == 204
    db.refresh(session)
    assert session.place_id is None  # back to the default place
