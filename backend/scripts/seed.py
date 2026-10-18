"""Generate a year of realistic synthetic data, to develop without any account.

Usage (from the repository root):
    make seed          # create or refresh the synthetic data
    make seed-clear    # remove it

Everything is written with ``source = "synthetic"``, so it never mixes with
your real Strava/Garmin data and can be deleted in one go. The random
generator has a fixed seed: running the script twice gives the same data, and
thanks to upserts it creates no duplicates.

The profile imitates the owner's week: running, cycling, strength sessions
and group classes at the gym, with realistic sleep and recovery variations.
"""

import argparse
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityStream,
    BodyMetric,
    DailyHealth,
    RawPayload,
    SleepNight,
)
from app.db.models.enums import DataSource
from app.db.session import get_session_factory
from app.integrations.health.provider import DailyHealthRecord, HealthBatch, SleepRecord
from app.repositories import activities as activities_repo
from app.services import polyline
from app.services.health_sync import store_batch
from app.services.stream_codec import encode_streams, point_count

SOURCE = DataSource.SYNTHETIC
LOCAL_TZ = ZoneInfo("Europe/Luxembourg")
# Starting points of routes, around Luxembourg City (lat, lng).
START_POINTS = [(49.6116, 6.1319), (49.6295, 6.1650), (49.5933, 6.1185), (49.6440, 6.1100)]


@dataclass
class PlannedSession:
    sport_type: str
    hour: int
    duration_min: float
    distance_km: float  # 0 for indoor sessions
    avg_hr: float


def weekly_plan(day: date, rng: random.Random) -> list[PlannedSession]:
    """What happens on ``day``: a typical week, with randomness and skipped sessions."""
    weekday = day.weekday()  # Monday = 0
    sessions: list[PlannedSession] = []
    if weekday == 0:  # Monday: strength
        sessions.append(PlannedSession("WeightTraining", 18, rng.uniform(50, 70), 0, 112))
    elif weekday == 1:  # Tuesday: easy run
        km = rng.uniform(7, 10)
        sessions.append(PlannedSession("Run", 7, km * rng.uniform(5.4, 5.9), km, 142))
    elif weekday == 2:  # Wednesday: group class at the gym
        sessions.append(
            PlannedSession(rng.choice(["Workout", "HighIntensityIntervalTraining"]), 19, 55, 0, 138)
        )
    elif weekday == 3:  # Thursday: strength or bike commute
        if rng.random() < 0.6:
            sessions.append(PlannedSession("WeightTraining", 18, rng.uniform(45, 65), 0, 110))
        else:
            km = rng.uniform(20, 30)
            sessions.append(PlannedSession("Ride", 17, km * rng.uniform(2.2, 2.6), km, 128))
    elif weekday == 5:  # Saturday: long run
        km = rng.uniform(12, 20)
        sessions.append(PlannedSession("Run", 9, km * rng.uniform(5.6, 6.1), km, 146))
    elif weekday == 6:  # Sunday: long ride
        km = rng.uniform(40, 80)
        sessions.append(PlannedSession("Ride", 10, km * rng.uniform(2.0, 2.4), km, 132))
    # Real life: about 15 % of planned sessions don't happen.
    return [s for s in sessions if rng.random() > 0.15]


def make_route(distance_km: float, rng: random.Random, points: int) -> list[tuple[float, float]]:
    """A closed loop of the right length, starting from one of the usual places."""
    start_lat, start_lng = rng.choice(START_POINTS)
    radius_km = distance_km / (2 * math.pi)
    km_per_deg_lat, km_per_deg_lng = 111.0, 111.0 * math.cos(math.radians(start_lat))
    route = []
    for i in range(points):
        angle = 2 * math.pi * i / max(points - 1, 1)
        wobble = 1 + 0.08 * math.sin(5 * angle)
        lat = start_lat + radius_km * wobble * (math.sin(angle)) / km_per_deg_lat
        lng = start_lng + radius_km * wobble * (1 - math.cos(angle)) / km_per_deg_lng
        route.append((round(lat, 6), round(lng, 6)))
    return route


def make_streams(
    session: PlannedSession, route: list[tuple[float, float]] | None, rng: random.Random
) -> dict[str, list[object]]:
    """Time series sampled every 10 s (real data is every second; 10 s keeps the seed light)."""
    samples = max(int(session.duration_min * 6), 2)
    streams: dict[str, list[object]] = {
        "time": [i * 10 for i in range(samples)],
        "heartrate": [
            round(
                session.avg_hr - 15 * math.exp(-i / 30) + 6 * math.sin(i / 25) + rng.uniform(-2, 2)
            )
            for i in range(samples)
        ],
    }
    if route:
        step = (len(route) - 1) / (samples - 1)
        streams["latlng"] = [list(route[round(i * step)]) for i in range(samples)]
        streams["altitude"] = [round(300 + 25 * math.sin(i / 40), 1) for i in range(samples)]
        streams["distance"] = [
            round(session.distance_km * 1000 * i / (samples - 1), 1) for i in range(samples)
        ]
    return streams


def seed_activities(db: Session, start: date, end: date, rng: random.Random) -> int:
    count = 0
    day = start
    while day <= end:
        for index, session in enumerate(weekly_plan(day, rng)):
            local_start = datetime(
                day.year, day.month, day.day, session.hour, rng.randint(0, 50), tzinfo=LOCAL_TZ
            )
            outdoor = session.distance_km > 0
            route = make_route(session.distance_km, rng, points=80) if outdoor else None
            duration_s = int(session.duration_min * 60)
            fields = {
                "name": f"{session.sport_type} {day.isoformat()}",
                "sport_type": session.sport_type,
                "start_time": local_start.astimezone(UTC),
                "timezone": "Europe/Luxembourg",
                "elapsed_time_s": duration_s + rng.randint(0, 300),
                "moving_time_s": duration_s,
                "distance_m": session.distance_km * 1000 if outdoor else None,
                "elevation_gain_m": round(session.distance_km * rng.uniform(5, 12), 1)
                if outdoor
                else None,
                "average_speed_mps": session.distance_km * 1000 / duration_s if outdoor else None,
                "average_heartrate": session.avg_hr + rng.uniform(-4, 4),
                "max_heartrate": session.avg_hr + rng.uniform(18, 30),
                "summary_polyline": polyline.encode(route) if route else None,
                "has_heartrate": True,
            }
            activity, _ = activities_repo.upsert_activity(
                db, SOURCE, f"syn-{day.isoformat()}-{index}", fields
            )
            streams = make_streams(session, route, rng)
            activities_repo.save_stream(
                db, activity, list(streams), point_count(streams), encode_streams(streams)
            )
            count += 1
        day += timedelta(days=1)
    db.commit()
    return count


def seed_health(db: Session, start: date, end: date, rng: random.Random) -> int:
    batch = HealthBatch()
    fitness_trend = 0.0  # resting HR slowly improves over the year
    day = start
    while day <= end:
        fitness_trend += 1 / 365
        bad_night = rng.random() < 0.12  # stress, late evening...
        duration_h = rng.uniform(5.0, 6.2) if bad_night else rng.uniform(6.6, 8.3)
        duration_s = int(duration_h * 3600)
        deep, rem = (
            int(duration_s * rng.uniform(0.13, 0.2)),
            int(duration_s * rng.uniform(0.18, 0.25)),
        )
        resting_hr = round(
            54 - 4 * fitness_trend + (4 if bad_night else 0) + rng.uniform(-1.5, 1.5)
        )
        hrv = round(58 + 8 * fitness_trend - (14 if bad_night else 0) + rng.uniform(-6, 6), 1)
        wake = datetime(day.year, day.month, day.day, 6, 30, tzinfo=LOCAL_TZ) + timedelta(
            minutes=rng.randint(-40, 60)
        )
        batch.sleep.append(
            SleepRecord(
                night_date=day,
                sleep_start=(wake - timedelta(seconds=duration_s)).astimezone(UTC),
                sleep_end=wake.astimezone(UTC),
                duration_s=duration_s,
                score=max(
                    30,
                    min(
                        98,
                        round(45 + 6 * duration_h - (12 if bad_night else 0) + rng.uniform(-5, 5)),
                    ),
                ),
                deep_s=deep,
                rem_s=rem,
                light_s=duration_s - deep - rem,
                awake_s=rng.randint(600, 2400),
                resting_heartrate=resting_hr,
                hrv_ms=hrv,
                body_battery_wake=max(
                    20, min(100, round(60 + 5 * duration_h - (20 if bad_night else 0)))
                ),
            )
        )
        batch.daily.append(
            DailyHealthRecord(
                day=day,
                resting_heartrate=resting_hr,
                hrv_ms=hrv,
                stress_avg=rng.randint(20, 45) + (10 if bad_night else 0),
                steps=rng.randint(5000, 14000),
                vo2max=round(49 + 2 * fitness_trend, 1),
                body_battery_max=rng.randint(70, 100),
                body_battery_min=rng.randint(5, 30),
            )
        )
        day += timedelta(days=1)
    store_batch(db, SOURCE, batch)
    return len(batch.sleep)


def seed_weight(db: Session, start: date, end: date, rng: random.Random) -> int:
    """A weigh-in about 4 days a week, slowly going from ~82 to ~79 kg.

    Days that already have a real (manual) weigh-in are left alone.
    """
    existing = {
        metric.measured_on: metric
        for metric in db.scalars(select(BodyMetric).where(BodyMetric.measured_on >= start))
    }
    total_days = max((end - start).days, 1)
    count = 0
    day = start
    while day <= end:
        progress = (day - start).days / total_days
        weight = round(82 - 3 * progress + rng.uniform(-0.6, 0.6), 1)
        measured = rng.random() < 0.6
        current = existing.get(day)
        if measured and (current is None or current.source == SOURCE):
            if current is None:
                current = BodyMetric(measured_on=day, source=SOURCE)
                db.add(current)
            current.weight_kg = weight
            current.waist_cm = round(88 - 3 * progress + rng.uniform(-0.5, 0.5), 1)
            count += 1
        day += timedelta(days=1)
    db.commit()
    return count


def clear(db: Session) -> None:
    activity_ids = select(Activity.id).where(Activity.source == SOURCE)
    db.execute(delete(ActivityStream).where(ActivityStream.activity_id.in_(activity_ids)))
    for model in (Activity, SleepNight, DailyHealth, RawPayload, BodyMetric):
        db.execute(delete(model).where(model.source == SOURCE))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=365, help="how many days back (default 365)")
    parser.add_argument("--clear", action="store_true", help="delete the synthetic data and stop")
    args = parser.parse_args()

    with get_session_factory()() as db:
        if args.clear:
            clear(db)
            print("Synthetic data removed.")
            return
        rng = random.Random(42)  # fixed seed = same data every time
        end = datetime.now(LOCAL_TZ).date()
        start = end - timedelta(days=args.days - 1)
        activities = seed_activities(db, start, end, rng)
        nights = seed_health(db, start, end, rng)
        weigh_ins = seed_weight(db, start, end, rng)
        print(
            f"Synthetic data ready: {activities} activities, {nights} nights and "
            f"{weigh_ins} weigh-ins ({start} to {end})."
        )


if __name__ == "__main__":
    main()
