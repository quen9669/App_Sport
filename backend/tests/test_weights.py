"""Weigh-ins from Garmin: mapping, storage rules and the carried-forward weight."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BodyMetric
from app.db.models.enums import DataSource
from app.integrations.health.garmin_connect import GarminConnectProvider, map_weights
from app.integrations.health.provider import HealthBatch, WeightRecord
from app.services.health_dashboard import health_days
from app.services.health_sync import store_batch
from tests.fixtures.garmin import FakeGarmin

TZ = "Europe/Luxembourg"


def weigh_in(day: str, grams: float, time_ms: int = 0, fat: float | None = None) -> dict[str, Any]:
    return {"calendarDate": day, "date": time_ms, "weight": grams, "bodyFat": fat}


def test_weights_are_converted_and_the_last_of_the_day_wins() -> None:
    records = map_weights(
        {
            "dateWeightList": [
                weigh_in("2026-10-12", 80_100.0, time_ms=2, fat=18.0),
                weigh_in("2026-10-12", 79_600.0, time_ms=1),
                weigh_in("2026-09-01", 81_000.0),
                weigh_in("2026-09-02", 5_000.0),  # 5 kg: a scale error, dropped
                {"calendarDate": "2026-09-03"},  # no weight at all
            ]
        }
    )
    assert [(r.day, r.weight_kg, r.body_fat_pct) for r in records] == [
        (date(2026, 9, 1), 81.0, None),
        (date(2026, 10, 12), 80.1, 18.0),
    ]
    assert map_weights(None) == []


def test_provider_looks_a_year_back_for_weigh_ins() -> None:
    fake = FakeGarmin()
    fake.weigh_ins = [weigh_in("2026-03-01", 82_000.0)]
    batch = GarminConnectProvider(login=lambda: fake).fetch_range(
        date(2026, 10, 16), date(2026, 10, 18)
    )
    assert fake.weight_range == ("2025-10-18", "2026-10-18")
    assert [w.weight_kg for w in batch.weights] == [82.0]


def test_garmin_weight_never_overwrites_a_weigh_in_typed_in_the_app(db: Session) -> None:
    db.add(BodyMetric(measured_on=date(2026, 10, 12), weight_kg=79.0, source=DataSource.MANUAL))
    db.add(BodyMetric(measured_on=date(2026, 10, 13), weight_kg=70.0, source="synthetic"))
    db.commit()
    batch = HealthBatch(
        weights=[
            WeightRecord(date(2026, 10, 12), 80.0),
            WeightRecord(date(2026, 10, 13), 80.5),
            WeightRecord(date(2026, 10, 14), 80.2),
        ]
    )

    store_batch(db, DataSource.GARMIN, batch)
    store_batch(db, DataSource.GARMIN, batch)  # idempotent

    rows = {m.measured_on.day: (m.weight_kg, m.source) for m in db.scalars(select(BodyMetric))}
    assert rows == {
        12: (79.0, "manual"),  # the typed value stays
        13: (80.5, "garmin"),  # test data is replaced
        14: (80.2, "garmin"),
    }


def test_last_weigh_in_is_carried_forward(db: Session) -> None:
    db.add(BodyMetric(measured_on=date(2026, 8, 20), weight_kg=81.0, source="garmin"))
    db.add(BodyMetric(measured_on=date(2026, 10, 15), weight_kg=79.5, source="garmin"))
    db.commit()

    days = health_days(db, date(2026, 10, 13), date(2026, 10, 17), TZ)

    assert [d.weight_kg for d in days] == [81.0, 81.0, 79.5, 79.5, 79.5]
    assert days[0].weight_measured_on == date(2026, 8, 20)
    assert days[-1].weight_measured_on == date(2026, 10, 15)


def test_no_weigh_in_at_all_means_no_weight(db: Session) -> None:
    days = health_days(db, date(2026, 10, 13), date(2026, 10, 14), TZ)
    assert all(d.weight_kg is None and d.weight_measured_on is None for d in days)
