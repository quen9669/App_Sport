"""Tests for the polyline codec and the synthetic data generator."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, SleepNight
from app.services import polyline
from scripts import seed


def test_polyline_matches_google_reference() -> None:
    # Example from Google's documentation of the algorithm.
    points = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]

    assert polyline.encode(points) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    assert polyline.decode("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == points


def test_seed_is_idempotent_and_clearable(db: Session) -> None:
    import random
    from datetime import date

    start, end = date(2026, 9, 1), date(2026, 9, 30)
    seed.seed_activities(db, start, end, random.Random(1))
    seed.seed_health(db, start, end, random.Random(1))
    activities = db.scalar(select(func.count()).select_from(Activity))
    seed.seed_activities(db, start, end, random.Random(1))

    assert activities and activities > 10
    assert db.scalar(select(func.count()).select_from(Activity)) == activities
    assert db.scalar(select(func.count()).select_from(SleepNight)) == 30

    seed.clear(db)
    assert db.scalar(select(func.count()).select_from(Activity)) == 0
