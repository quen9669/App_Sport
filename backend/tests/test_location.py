"""Town and country of activities, map dots, motorcycle trips."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity, Place
from app.integrations.health.garmin_activities import GarminActivitySummary, activity_fields
from app.integrations.strava.mappers import StravaActivitySummary
from app.integrations.strava.mappers import activity_fields as strava_fields
from app.services.activity_location import Locator
from app.services.activity_map import MapFilters, map_routes
from app.services.classification import Category, effective_category
from app.services.countries import country_at
from app.services.training_load import HeartRateParams, activity_load
from tests.fixtures.garmin import garmin_activity


def test_country_of_points_around_luxembourg() -> None:
    assert country_at(49.6116, 6.1319) == "LU"  # Luxembourg city
    assert country_at(49.47, 6.36) == "DE"  # Perl, just across the Moselle
    assert country_at(50.85, 4.35) == "BE"  # Brussels
    assert country_at(48.85, 2.35) == "FR"  # Paris (France has overseas parts too)
    assert country_at(45.62, -1.03) == "FR"  # Royan beach, on the coastline
    assert country_at(46.0, -30.0) is None  # middle of the Atlantic
    assert country_at(None, 6.13) is None


def test_source_town_and_start_point_are_mapped() -> None:
    start = datetime(2026, 10, 12, 6, 30, tzinfo=UTC)
    garmin = activity_fields(GarminActivitySummary.model_validate(garmin_activity(1, start)))
    assert (garmin["location_name"], garmin["start_latitude"]) == ("Luxembourg", 49.6116)
    strava = strava_fields(
        StravaActivitySummary.model_validate(
            {"id": 1, "start_date": start, "elapsed_time": 60, "start_latlng": [49.6, 6.1]}
        )
    )
    assert (strava["location_name"], strava["start_latitude"], strava["start_longitude"]) == (
        None,
        49.6,
        6.1,
    )


def _activity(db: Session, external_id: str, **fields: object) -> Activity:
    values: dict[str, object] = {
        "name": f"Activity {external_id}",
        "sport_type": "running",
        "start_time": datetime.now(UTC) - timedelta(days=1),
        "elapsed_time_s": 1800,
    }
    activity = Activity(source="garmin", external_id=external_id, **(values | fields))
    db.add(activity)
    db.commit()
    return activity


def _gym(db: Session) -> Place:
    # Tests build the tables from the models: the migration's gyms are not there.
    gym = Place(
        name="Jims Gare", latitude=49.6, longitude=6.13, city="Luxembourg", role="strength_default"
    )
    db.add(gym)
    db.commit()
    return gym


def test_gym_session_takes_the_town_and_country_of_its_place(db: Session) -> None:
    gym = _gym(db)
    session = _activity(db, "1", sport_type="strength_training")
    trip = _activity(db, "2", location_name="Royan", start_latitude=45.62, start_longitude=-1.02)
    locator = Locator(db)
    assert locator.locate(session).city == gym.city == "Luxembourg"
    assert locator.locate(session).country_code == "LU"
    assert (locator.locate(trip).city, locator.locate(trip).country_code) == ("Royan", "FR")


def test_activity_with_a_start_but_no_route_is_a_dot_not_a_gym(db: Session) -> None:
    """Garmin routes come later with the details: the start point is shown meanwhile."""
    _gym(db)
    run = _activity(db, "1", distance_m=5000, start_latitude=49.6, start_longitude=6.1)
    _activity(db, "2", sport_type="strength_training")
    result = map_routes(db, MapFilters(), None, 12)
    assert [p.activity.id for p in result.points] == [run.id]
    assert [len(p.activities) for p in result.places] == [1]  # only the gym session
    assert result.total == 2


def test_motorcycle_trip_is_transport_without_training_load(db: Session) -> None:
    trip = _activity(
        db, "1", sport_type="motorcycling_v2", distance_m=328_989, average_heartrate=95
    )
    assert effective_category(trip) == Category.TRANSPORT
    params = HeartRateParams(max_hr=190, resting_hr=50, sex="male")
    assert activity_load(trip, params) == (0.0, False)


def test_rows_carry_town_country_and_sport(client: TestClient, db: Session) -> None:
    _activity(
        db,
        "1",
        sport_type="walking",
        location_name="Luxembourg",
        start_latitude=49.6116,
        start_longitude=6.1319,
    )
    body = client.get("/api/goals/progress").json()
    row = body["activities"][0]
    assert (row["city"], row["country_code"], row["sport"]) == ("Luxembourg", "LU", "walk")

    routes = client.get("/api/map/routes", params={"days": 14}).json()
    assert routes["points"][0]["country_code"] == "LU"
