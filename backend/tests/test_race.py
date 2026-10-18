"""Race predictor: Daniels' tables, Riegel, pacing, form estimate, routes."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity
from app.db.models.enums import DataSource
from app.repositories import activities as activities_repo
from app.repositories import profile as profile_repo
from app.services.race import daniels, plan, riegel
from app.services.race.efforts import (
    HeartRate,
    Method,
    RunEffort,
    Status,
    best_segment,
    estimate_form,
    heart_rate_vdot,
    pace_variation,
    usable,
)
from app.services.race.predictor import efforts_of
from app.services.stream_codec import encode_streams

TODAY = date(2026, 10, 18)


def minutes(text: str) -> float:
    """'1:31:35' or '19:57' to seconds."""
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


# --- Daniels' VDOT, against his published tables ---------------------------------

# VDOT -> 5 km, 10 km, half marathon, marathon (Daniels' Running Formula, 3rd ed.).
PUBLISHED = {
    40: ("24:08", "50:03", "1:50:59", "3:49:45"),
    50: ("19:57", "41:21", "1:31:35", "3:10:49"),
    60: ("17:03", "35:22", "1:18:09", "2:43:25"),
}
DISTANCES = (5000.0, 10_000.0, 21_097.5, 42_195.0)


@pytest.mark.parametrize("value", PUBLISHED)
def test_race_times_match_the_published_tables(value: int) -> None:
    for distance, expected in zip(DISTANCES, PUBLISHED[value], strict=True):
        predicted = daniels.race_time(value, distance)
        # Within 0.5 %: the tables are rounded, and Daniels smoothed some values.
        assert predicted == pytest.approx(minutes(expected), rel=0.005), (value, distance)


def test_vdot_of_a_race_is_the_inverse_of_race_time() -> None:
    assert daniels.vdot(5000, minutes("20:00")) == pytest.approx(49.8, abs=0.1)
    for value in (35.0, 47.3, 62.0):
        assert daniels.vdot(10_000, daniels.race_time(value, 10_000)) == pytest.approx(value)


def test_ten_km_in_fifty_minutes_needs_a_vdot_of_about_40() -> None:
    # FRANKS's goal for 13 December 2026.
    assert daniels.vdot(10_000, minutes("50:00")) == pytest.approx(40.0, abs=0.1)


def test_training_paces_at_vdot_50() -> None:
    zones = {zone.key: zone for zone in daniels.training_paces(50)}
    # Published: easy 5:08-5:38, marathon 4:31, threshold 4:15, interval 4:00, repetition 3:41.
    assert zones["easy"].slow_s_per_km == pytest.approx(minutes("5:38"), abs=3)
    assert zones["easy"].fast_s_per_km == pytest.approx(minutes("5:08"), abs=3)
    assert zones["marathon"].fast_s_per_km == pytest.approx(minutes("4:31"), abs=3)
    assert zones["threshold"].fast_s_per_km == pytest.approx(minutes("4:15"), abs=3)
    assert zones["interval"].fast_s_per_km == pytest.approx(minutes("4:00"), abs=3)
    assert zones["repetition"].fast_s_per_km == pytest.approx(minutes("3:41"), abs=3)
    paces = [zone.fast_s_per_km for zone in daniels.training_paces(50)]
    assert paces == sorted(paces, reverse=True)  # slowest first


def test_invalid_inputs_are_refused() -> None:
    with pytest.raises(ValueError):
        daniels.vdot(0, 100)
    with pytest.raises(ValueError):
        daniels.race_time(-1, 5000)
    with pytest.raises(ValueError):
        riegel.riegel_time(5000, 0, 10_000)


# --- Riegel -------------------------------------------------------------------


def test_riegel() -> None:
    # 20:00 on 5 km -> 20 x 2^1.06 = 41:42 on 10 km.
    assert riegel.riegel_time(5000, 1200, 10_000) == pytest.approx(1200 * 2**1.06)
    assert riegel.riegel_time(5000, 1200, 5000) == 1200
    # A higher exponent (less endurance) gives a slower time.
    assert riegel.riegel_time(5000, 1200, 42_195, 1.10) > riegel.riegel_time(5000, 1200, 42_195)


# --- Pace plan and feasibility -------------------------------------------------------


def test_pace_plan_negative_split_on_a_flat_10_km() -> None:
    result = plan.pace_plan(10_000, 3000)
    assert len(result.splits) == 10
    assert result.average_pace_s_per_km == 300
    assert result.splits[0].pace_s_per_km == pytest.approx(303)  # 1 % slower at first
    assert result.splits[-1].pace_s_per_km == pytest.approx(297)  # 1 % faster at the end
    assert result.splits[4].elapsed_s == pytest.approx(5 * 303)  # half-way: 25:15
    assert result.splits[-1].elapsed_s == 3000  # exactly on target


def test_pace_plan_half_marathon_with_hills() -> None:
    result = plan.pace_plan(21_097.5, 6000, elevation_gain_m=150)
    assert result.hill_allowance_s == 90  # 150 m x 0.6 s
    assert result.target_time_s == 6090
    assert len(result.splits) == 22
    assert result.splits[-1].km == pytest.approx(21.098, abs=0.001)  # the last split is partial
    assert result.splits[-1].elapsed_s == 6090


@pytest.mark.parametrize(
    ("target", "verdict"),
    [
        (3100, plan.Feasibility.REALISTIC),  # slower than predicted
        (3000, plan.Feasibility.REALISTIC),
        (2950, plan.Feasibility.AMBITIOUS),  # between the prediction and the fast end
        (2860, plan.Feasibility.AMBITIOUS),  # just beyond the fast end (2 % margin)
        (2800, plan.Feasibility.UNLIKELY),
    ],
)
def test_feasibility(target: float, verdict: plan.Feasibility) -> None:
    result = plan.feasibility(target, predicted_s=3000, fastest_s=2900)
    assert result.verdict is verdict
    assert result.gap_s == target - 3000


# --- Efforts and form estimate -------------------------------------------------------

HR = HeartRate(max_hr=190, resting_hr=50)


def effort(
    activity_id: int, days_ago: int, km: float = 10, pace: str = "6:00", **fields: Any
) -> RunEffort:
    return RunEffort(
        activity_id=activity_id,
        day=TODAY - timedelta(days=days_ago),
        distance_m=km * 1000,
        time_s=minutes(pace) * km,
        **fields,
    )


def test_usable_skips_short_hilly_irregular_and_old_runs() -> None:
    assert usable(effort(1, 10), TODAY)
    assert not usable(effort(1, 10, km=2.5), TODAY)
    assert not usable(effort(1, 10, elevation_gain_m=200), TODAY)  # 20 m/km
    assert not usable(effort(1, 10, pace_variation=0.2), TODAY)  # intervals
    assert not usable(effort(1, 121), TODAY)
    assert not usable(effort(1, -1), TODAY)


def test_heart_rate_gives_a_higher_vdot_for_an_easy_run() -> None:
    # 10 km at 6:00/km with 150 bpm (71 % of the heart-rate reserve).
    easy = effort(1, 0, average_hr=150)
    as_race = daniels.vdot(easy.distance_m, easy.time_s)
    from_hr = heart_rate_vdot(easy, HR)
    assert from_hr is not None and from_hr > as_race + 5
    # Too easy (55 %) or a race effort (98 %): no estimate from heart rate.
    assert heart_rate_vdot(effort(1, 0, average_hr=127), HR) is None
    assert heart_rate_vdot(effort(1, 0, average_hr=188), HR) is None
    assert heart_rate_vdot(easy, None) is None


def test_estimate_needs_three_recent_runs() -> None:
    result = estimate_form([effort(1, 5), effort(2, 8)], HR, TODAY)
    assert result.status is Status.INSUFFICIENT
    assert result.reason is not None and "2 sur les 120 derniers jours" in result.reason
    old = [effort(i, 70 + i) for i in range(5)]
    stale = estimate_form(old, HR, TODAY)
    assert stale.status is Status.INSUFFICIENT
    assert stale.reason is not None and "70 jours" in stale.reason


def test_estimate_uses_the_better_half_and_gives_a_range() -> None:
    runs = [
        effort(1, 3, pace="5:00"),
        effort(2, 6, pace="5:05"),
        effort(3, 9, pace="5:10"),
        effort(4, 12, pace="6:30"),  # an easy jog: says "at least", not "exactly"
        effort(5, 15, pace="6:40"),
        effort(6, 18, pace="6:45"),
    ]
    result = estimate_form(runs, None, TODAY)
    assert result.status is Status.OK
    assert result.vdot is not None and result.low is not None and result.high is not None
    best = daniels.vdot(10_000, minutes("5:00") * 10)
    third = daniels.vdot(10_000, minutes("5:10") * 10)
    assert third < result.vdot < best  # the jogs do not pull the estimate down
    assert result.low < result.vdot < result.high
    assert result.high - result.low >= 2  # at least one VDOT point each way
    assert [e.used for e in result.efforts] == [True, True, True, False, False, False]
    assert all(e.method is Method.RACE for e in result.efforts)


def test_recent_efforts_weigh_more() -> None:
    result = estimate_form([effort(1, 0), effort(2, 45), effort(3, 90)], None, TODAY)
    weights = sorted(e.weight for e in result.efforts)
    assert weights == pytest.approx([0.25, 0.5, 1.0])


def test_one_run_counts_once_even_with_its_segments() -> None:
    whole = effort(1, 2, km=12, pace="5:30")
    segment = effort(1, 2, km=5, pace="5:00", segment=True)
    result = estimate_form([whole, segment, effort(2, 4), effort(3, 6)], None, TODAY)
    assert result.status is Status.OK
    ids = [e.effort.activity_id for e in result.efforts]
    assert sorted(ids) == [1, 2, 3]
    first = next(e for e in result.efforts if e.effort.activity_id == 1)
    assert first.effort.segment  # the 5 km gives the higher VDOT here


# --- Helpers on streams ----------------------------------------------------------------


def steady_stream(
    km: float, pace_s: float, start_s: float = 0.0
) -> tuple[list[float], list[float]]:
    """One sample every 10 s at a constant pace."""
    speed = 1000 / pace_s
    count = int(km * 1000 / speed / 10) + 1
    times = [start_s + 10 * i for i in range(count)]
    return times, [10 * i * speed for i in range(count)]


def test_best_segment_finds_the_fast_part() -> None:
    # 3 km at 6:00/km, then 5 km at 5:00/km.
    times_a, dist_a = steady_stream(3, 360)
    times_b, dist_b = steady_stream(5, 300)
    times = times_a + [times_a[-1] + t for t in times_b[1:]]
    dist = dist_a + [dist_a[-1] + d for d in dist_b[1:]]
    assert best_segment(times, dist, 5000) == pytest.approx(1500, abs=10)
    assert best_segment(times, dist, 20_000) is None


def test_pace_variation() -> None:
    times, dist = steady_stream(6, 300, start_s=120)  # a stream that does not start at 0 s
    steady = pace_variation(times, dist)
    assert steady is not None and steady < 0.02
    # Alternate 1 km fast, 1 km slow (intervals).
    times, dist, clock, covered = [0.0], [0.0], 0.0, 0.0
    for lap in range(6):
        pace = 240 if lap % 2 == 0 else 420
        for _ in range(10):
            clock += pace / 10
            covered += 100
            times.append(clock)
            dist.append(covered)
    irregular = pace_variation(times, dist)
    assert irregular is not None and irregular > 0.12
    assert pace_variation(*steady_stream(2, 300)) is None  # too short


# --- From the database ------------------------------------------------------------------


def add_run(
    db: Session,
    external_id: str,
    days_ago: int,
    km: float = 10,
    pace_s: float = 330,
    **fields: Any,
) -> Activity:
    values: dict[str, Any] = {
        "name": f"Course {external_id}",
        "sport_type": "running",
        "start_time": datetime.now(UTC) - timedelta(days=days_ago),
        "elapsed_time_s": round(km * pace_s) + 60,
        "moving_time_s": round(km * pace_s),
        "distance_m": km * 1000,
        "elevation_gain_m": 20,
    }
    values.update(fields)
    activity, _ = activities_repo.upsert_activity(db, DataSource.GARMIN, external_id, values)
    db.commit()
    return activity


def test_efforts_of_a_run_with_streams(db: Session) -> None:
    run = add_run(db, "1", days_ago=2, km=12, pace_s=330)
    times, dist = steady_stream(12, 330)
    data = encode_streams({"time": times, "distance": dist})
    activities_repo.save_stream(db, run, ["time", "distance"], len(times), data)
    db.commit()
    db.refresh(run)
    found = efforts_of(run, "Europe/Luxembourg")
    assert [(e.distance_m, e.segment) for e in found] == [
        (12_000, False),
        (5000, True),
        (10_000, True),
    ]
    assert found[0].time_s == 12 * 330  # moving time
    assert found[0].pace_variation is not None and found[0].pace_variation < 0.02
    assert found[1].time_s == pytest.approx(5 * 330, abs=10)


def test_race_route_insufficient_then_ok(client: TestClient, db: Session) -> None:
    add_run(db, "1", days_ago=3)
    body = client.get("/api/race").json()
    assert body["form"]["status"] == "insufficient"
    assert body["predictions"] == [] and body["zones"] == []

    add_run(db, "2", days_ago=5, pace_s=320)
    add_run(db, "3", days_ago=8, pace_s=340)
    add_run(db, "4", days_ago=9, sport_type="cycling")  # not a run
    add_run(db, "5", days_ago=10, hidden=True)
    add_run(db, "6", days_ago=11, is_trainer=True)  # treadmill
    body = client.get("/api/race").json()
    assert body["form"]["status"] == "ok"
    assert len(body["form"]["efforts"]) == 3
    assert [p["label"] for p in body["predictions"]] == [
        "5 km",
        "10 km",
        "Semi-marathon",
        "Marathon",
    ]
    ten = body["predictions"][1]
    assert ten["fastest_s"] < ten["time_s"] < ten["slowest_s"]
    assert [z["key"] for z in body["zones"]][0] == "easy"


def test_heart_rate_from_the_profile_is_used(client: TestClient, db: Session) -> None:
    profile = profile_repo.get_or_create_profile(db)
    profile.max_heartrate, profile.resting_heartrate = 190, 50
    db.commit()
    for i in range(3):
        add_run(db, str(i), days_ago=2 + i, pace_s=360, average_heartrate=150)
    body = client.get("/api/race").json()
    assert {e["method"] for e in body["form"]["efforts"]} == {"heart_rate"}


def test_target_race_plan_and_feasibility(client: TestClient, db: Session) -> None:
    for i in range(4):
        add_run(db, str(i), days_ago=2 + 3 * i, pace_s=300)  # 10 km at 5:00/km
    race_day = (datetime.now(UTC) + timedelta(days=56)).date()
    target = {"name": "Corrida", "distance_m": 10_000, "race_date": race_day.isoformat()}
    body = client.put("/api/race/target", json={**target, "target_time_s": 2940}).json()
    result = body["target"]
    assert result["name"] == "Corrida"
    assert 55 <= result["days_left"] <= 57
    assert result["required_vdot"] == pytest.approx(daniels.vdot(10_000, 2940))
    assert result["feasibility"]["verdict"] in {"realistic", "ambitious"}
    assert len(result["pace_plan"]["splits"]) == 10
    assert result["pace_plan"]["target_time_s"] == 2940

    # Hills: the target is a race-day time, so the flat-equivalent is faster.
    body = client.put(
        "/api/race/target", json={**target, "target_time_s": 2940, "elevation_gain_m": 100}
    ).json()
    assert body["target"]["pace_plan"]["hill_allowance_s"] == 60
    assert body["target"]["required_vdot"] == pytest.approx(daniels.vdot(10_000, 2880))

    # Without a target time: a plan on the predicted time, no verdict.
    body = client.put("/api/race/target", json=target).json()
    assert body["target"]["feasibility"] is None
    assert body["target"]["pace_plan"]["target_time_s"] == pytest.approx(
        body["target"]["predicted_s"]
    )

    assert client.delete("/api/race/target").json()["target"] is None


def test_target_validation(client: TestClient) -> None:
    far = (datetime.now(UTC) + timedelta(days=1000)).date().isoformat()
    assert (
        client.put("/api/race/target", json={"distance_m": 10_000, "race_date": far}).status_code
        == 422
    )
    soon = (datetime.now(UTC) + timedelta(days=10)).date().isoformat()
    short = {"distance_m": 100, "race_date": soon}
    assert client.put("/api/race/target", json=short).status_code == 422


def test_exclude_a_run(client: TestClient, db: Session) -> None:
    runs = [add_run(db, str(i), days_ago=2 + i) for i in range(3)]
    body = client.patch(f"/api/race/efforts/{runs[0].id}", json={"excluded": True}).json()
    assert body["form"]["status"] == "insufficient"
    assert [run["activity_id"] for run in body["form"]["excluded"]] == [runs[0].id]
    body = client.patch(f"/api/race/efforts/{runs[0].id}", json={"excluded": False}).json()
    assert body["form"]["status"] == "ok"
    assert client.patch("/api/race/efforts/999", json={"excluded": True}).status_code == 404
