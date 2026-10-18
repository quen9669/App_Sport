"""Goals CRUD, weekly progress and manual category correction."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity, Goal

_counter = 0


def add_activity(
    db: Session,
    sport_type: str,
    start: datetime,
    moving_min: int = 60,
    distance_km: float | None = None,
) -> Activity:
    global _counter
    _counter += 1
    activity = Activity(
        source="strava",
        external_id=str(_counter),
        name=f"{sport_type} {_counter}",
        sport_type=sport_type,
        start_time=start,
        elapsed_time_s=moving_min * 60,
        moving_time_s=moving_min * 60,
        distance_m=distance_km * 1000 if distance_km else None,
    )
    db.add(activity)
    db.commit()
    return activity


def add_goal(db: Session, kind: str, target: float, sport: str | None = None) -> Goal:
    goal = Goal(kind=kind, target=target, sport=sport, start_date=date(2026, 1, 1))
    db.add(goal)
    db.commit()
    return goal


def test_create_list_update_delete_goal(client: TestClient) -> None:
    created = client.post("/api/goals", json={"kind": "strength_sessions", "target": 3})
    assert created.status_code == 201
    goal = created.json()
    assert goal["status"] == "active"
    assert goal["start_date"] == date.today().isoformat()

    assert len(client.get("/api/goals").json()) == 1

    paused = client.patch(f"/api/goals/{goal['id']}", json={"status": "paused"})
    assert paused.json()["status"] == "paused"
    assert paused.json()["target"] == 3

    assert client.delete(f"/api/goals/{goal['id']}").status_code == 204
    assert client.get("/api/goals").json() == []
    assert client.delete(f"/api/goals/{goal['id']}").status_code == 404


def test_goal_bounds_are_checked(client: TestClient) -> None:
    too_many = client.post("/api/goals", json={"kind": "cardio_sessions", "target": 20})
    assert too_many.status_code == 422
    sport_on_sessions = client.post(
        "/api/goals", json={"kind": "cardio_sessions", "target": 3, "sport": "run"}
    )
    assert sport_on_sessions.status_code == 422
    unknown = client.post("/api/goals", json={"kind": "pushups", "target": 3})
    assert unknown.status_code == 422

    goal = client.post("/api/goals", json={"kind": "distance_km", "target": 20, "sport": "run"})
    patched = client.patch(f"/api/goals/{goal.json()['id']}", json={"target": 5000})
    assert patched.status_code == 422


def test_week_progress_counts_by_category(client: TestClient, db: Session) -> None:
    strength = add_goal(db, "strength_sessions", 3)
    cardio = add_goal(db, "cardio_sessions", 3)
    minutes = add_goal(db, "active_minutes", 150)
    run_km = add_goal(db, "distance_km", 20, sport="run")

    # Week 42 of 2026: Monday 12 to Sunday 18 October.
    add_activity(db, "WeightTraining", datetime(2026, 10, 12, 17, 0, tzinfo=UTC), 60)
    body_pump = add_activity(db, "Workout", datetime(2026, 10, 14, 18, 0, tzinfo=UTC), 45)
    # Two sessions on the same day both count.
    add_activity(db, "Run", datetime(2026, 10, 17, 8, 0, tzinfo=UTC), 50, distance_km=10.2)
    add_activity(db, "Ride", datetime(2026, 10, 17, 15, 0, tzinfo=UTC), 90, distance_km=40)
    add_activity(db, "Yoga", datetime(2026, 10, 16, 7, 0, tzinfo=UTC), 30)
    # Sunday 23:30 in Luxembourg (21:30 UTC) is still this week...
    add_activity(db, "Run", datetime(2026, 10, 18, 21, 30, tzinfo=UTC), 30, distance_km=6)
    # ...but Monday 00:30 local (22:30 UTC on Sunday) is next week.
    add_activity(db, "Run", datetime(2026, 10, 18, 22, 30, tzinfo=UTC), 30, distance_km=6)

    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    assert body["monday"] == "2026-10-12"
    by_goal = {item["goal"]["id"]: item for item in body["goals"]}
    assert by_goal[strength.id]["done"] == 2
    assert by_goal[strength.id]["achieved"] is False
    assert by_goal[cardio.id]["done"] == 3
    assert by_goal[cardio.id]["achieved"] is True
    assert by_goal[minutes.id]["done"] == 60 + 45 + 50 + 90 + 30  # yoga does not count
    assert by_goal[run_km.id]["done"] == 16.2  # the ride does not count for running
    assert len(body["activities"]) == 6

    # Correct the Body Pump class to cardio: it moves from one goal to the other.
    corrected = client.patch(
        f"/api/activities/{body_pump.id}/category", json={"category": "cardio"}
    )
    assert corrected.json() == {
        "id": body_pump.id,
        "category": "cardio",
        "automatic_category": "strength",
        "overridden": True,
    }
    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    by_goal = {item["goal"]["id"]: item for item in body["goals"]}
    assert by_goal[strength.id]["done"] == 1
    assert by_goal[cardio.id]["done"] == 4

    # Going back to the automatic category removes the correction.
    reset = client.patch(f"/api/activities/{body_pump.id}/category", json={"category": None})
    assert reset.json()["overridden"] is False


def test_paused_and_future_goals_are_not_counted(client: TestClient, db: Session) -> None:
    add_goal(db, "strength_sessions", 3).status = "paused"
    db.commit()
    future = Goal(kind="cardio_sessions", target=2, start_date=date(2027, 1, 4))
    db.add(future)
    db.commit()
    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    assert body["goals"] == []


def test_progress_rejects_bad_week(client: TestClient) -> None:
    assert client.get("/api/goals/progress", params={"week": "2026-W99"}).status_code == 422


def test_progress_defaults_to_current_week(client: TestClient) -> None:
    body = client.get("/api/goals/progress").json()
    assert body["week"].startswith(str(date.today().isocalendar().year))


def test_category_of_unknown_activity(client: TestClient) -> None:
    response = client.patch("/api/activities/999/category", json={"category": "cardio"})
    assert response.status_code == 404


def test_hide_an_activity_removes_it_from_goals(client: TestClient, db: Session) -> None:
    from app.repositories import activities as activities_repo

    client.post("/api/goals", json={"kind": "cardio_sessions", "target": 3})
    activity, _ = activities_repo.upsert_activity(
        db,
        "strava",
        "1",
        {
            "name": "Run",
            "sport_type": "Run",
            "start_time": datetime.now(UTC),
            "elapsed_time_s": 1800,
        },
    )
    db.commit()

    response = client.patch(f"/api/activities/{activity.id}/hidden", json={"hidden": True})
    assert response.json() == {"id": activity.id, "hidden": True}

    progress = client.get("/api/goals/progress").json()
    assert progress["goals"][0]["done"] == 0
    listed = progress["activities"][0]
    assert listed["hidden"] is True
    assert listed["possible_duplicate"] is False
    assert listed["source"] == "strava"
    assert client.patch("/api/activities/999/hidden", json={"hidden": True}).status_code == 404
