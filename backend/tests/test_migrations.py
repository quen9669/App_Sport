"""The Alembic migrations must build exactly the schema described by the models.

If someone changes a model and forgets to generate a migration, this test fails.
"""

import json
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from alembic import command
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert differences == []


def test_downgrade_removes_everything(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")


def test_intensity_minutes_are_read_back_from_raw_payloads(tmp_path: Path) -> None:
    """Days synced before the intensity columns existed get them from raw_payload."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "5bf6d8c96b49")  # the revision just before

    engine = create_engine(url)
    stats = {"stats": {"moderateIntensityMinutes": 25, "vigorousIntensityMinutes": 12}}
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO daily_health (source, day, created_at, updated_at) "
                "VALUES ('garmin', '2026-10-17', '2026-10-17', '2026-10-17')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO raw_payload (source, kind, external_id, payload, fetched_at) "
                "VALUES ('garmin', 'daily_health', '2026-10-17', :payload, '2026-10-17')"
            ),
            {"payload": json.dumps(stats)},
        )
    command.upgrade(config, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT intensity_moderate_min, intensity_vigorous_min FROM daily_health")
        ).one()
    engine.dispose()
    assert tuple(row) == (25, 12)


def test_activity_town_and_start_are_read_back_from_raw_payloads(tmp_path: Path) -> None:
    """Activities synced before the location columns existed get them from raw_payload."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "c32f1c56a3a9")  # the revision just before

    engine = create_engine(url)
    garmin = {"locationName": "Royan", "startLatitude": 45.62, "startLongitude": -1.02}
    strava: dict[str, object] = {"location_city": None, "start_latlng": []}  # Strava without GPS
    with engine.begin() as connection:
        for source, external_id in (("garmin", "1"), ("strava", "2")):
            connection.execute(
                text(
                    "INSERT INTO activity (source, external_id, name, sport_type, start_time, "
                    "elapsed_time_s, has_heartrate, is_manual, is_trainer, hidden, "
                    "created_at, updated_at) VALUES (:source, :id, 'x', 'running', "
                    "'2026-10-17', 60, 0, 0, 0, 0, '2026-10-17', '2026-10-17')"
                ),
                {"source": source, "id": external_id},
            )
        for source, external_id, payload in (("garmin", "1", garmin), ("strava", "2", strava)):
            connection.execute(
                text(
                    "INSERT INTO raw_payload (source, kind, external_id, payload, fetched_at) "
                    "VALUES (:source, 'activity', :id, :payload, '2026-10-17')"
                ),
                {"source": source, "id": external_id, "payload": json.dumps(payload)},
            )
    command.upgrade(config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT source, location_name, start_latitude, start_longitude FROM activity "
                "ORDER BY source"
            )
        ).all()
        cities = connection.execute(text("SELECT city FROM place")).scalars().all()
    engine.dispose()
    assert [tuple(r) for r in rows] == [
        ("garmin", "Royan", 45.62, -1.02),
        ("strava", None, None, None),
    ]
    assert cities == ["Luxembourg", "Luxembourg"]  # the two default gyms


def test_floors_are_read_back_from_raw_payloads(tmp_path: Path) -> None:
    """Days synced before the floor columns existed get them from raw_payload."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "4ae8dc6985f1")  # the revision just before

    engine = create_engine(url)
    stats = {"stats": {"floorsAscended": 12.4, "floorsDescended": 9.6}}
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO daily_health (source, day, created_at, updated_at) "
                "VALUES ('garmin', '2026-10-17', '2026-10-17', '2026-10-17')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO raw_payload (source, kind, external_id, payload, fetched_at) "
                "VALUES ('garmin', 'daily_health', '2026-10-17', :payload, '2026-10-17')"
            ),
            {"payload": json.dumps(stats)},
        )
    command.upgrade(config, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT floors_ascended, floors_descended FROM daily_health")
        ).one()
    engine.dispose()
    assert tuple(row) == (12, 10)
