"""Tests for the polyline codec and the synthetic data generator."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, BodyMetric, SleepNight, StrengthSession, StrengthSet
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


def test_seed_weight_keeps_manual_weigh_ins(db: Session) -> None:
    import random
    from datetime import date

    manual = BodyMetric(measured_on=date(2026, 9, 10), weight_kg=77.7, source="manual")
    db.add(manual)
    db.commit()

    count = seed.seed_weight(db, date(2026, 9, 1), date(2026, 9, 30), random.Random(1))
    assert count > 10
    assert db.get(BodyMetric, manual.id).weight_kg == 77.7  # type: ignore[union-attr]

    seed.clear(db)
    remaining = list(db.scalars(select(BodyMetric)))
    assert [m.weight_kg for m in remaining] == [77.7]


def test_seed_strength_links_sessions_and_clears_them(db: Session) -> None:
    import random
    from datetime import date

    seed.seed_activities(db, date(2026, 9, 1), date(2026, 9, 30), random.Random(1))
    created = seed.seed_strength(db, random.Random(1))
    assert created > 0
    assert seed.seed_strength(db, random.Random(1)) == 0  # idempotent
    session = db.scalars(select(StrengthSession)).first()
    assert session is not None and session.activity_id is not None
    assert {s.exercise for s in session.sets} >= {"Squat", "Tractions"}

    seed.clear(db)
    assert db.scalar(select(func.count()).select_from(StrengthSession)) == 0
    assert db.scalar(select(func.count()).select_from(StrengthSet)) == 0
