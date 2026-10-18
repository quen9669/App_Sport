"""Strength sessions: typing sets, last loads, and counting each gym session once."""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity, Goal, StrengthSession
from app.services.goals import streak, weeks_history
from app.services.weeks import parse_week

SESSION = {
    "performed_at": "2026-10-14T18:00:00+02:00",
    "duration_min": 60,
    "sets": [
        {"exercise": "Squat", "reps": 8, "weight_kg": 80},
        {"exercise": "Squat", "reps": 8, "weight_kg": 80, "rpe": 8},
        {"exercise": " Développé  couché ", "reps": 10, "weight_kg": 60},
        {"exercise": "Tractions", "reps": 6},
    ],
}


def add_activity(db: Session, sport_type: str, start: datetime, minutes: int = 60) -> Activity:
    activity = Activity(
        source="strava",
        external_id=f"{sport_type}-{start.isoformat()}",
        name=sport_type,
        sport_type=sport_type,
        start_time=start,
        elapsed_time_s=minutes * 60,
        moving_time_s=minutes * 60,
    )
    db.add(activity)
    db.commit()
    return activity


def add_goal(db: Session, kind: str, target: float) -> Goal:
    goal = Goal(kind=kind, target=target, start_date=date(2026, 1, 1))
    db.add(goal)
    db.commit()
    return goal


def test_create_session_numbers_sets_per_exercise(client: TestClient) -> None:
    response = client.post("/api/strength/sessions", json=SESSION)
    assert response.status_code == 201
    body = response.json()
    assert body["performed_at"] == "2026-10-14T16:00:00Z"  # stored in UTC
    assert [(s["exercise"], s["set_number"]) for s in body["sets"]] == [
        ("Squat", 1),
        ("Squat", 2),
        ("Développé couché", 1),  # spaces cleaned up
        ("Tractions", 1),
    ]
    assert body["sets"][3]["weight_kg"] is None  # body weight

    listed = client.get("/api/strength/sessions").json()
    assert [s["id"] for s in listed] == [body["id"]]


def test_replace_and_delete_session(client: TestClient) -> None:
    session_id = client.post("/api/strength/sessions", json=SESSION).json()["id"]
    replaced = client.put(
        f"/api/strength/sessions/{session_id}",
        json={**SESSION, "sets": [{"exercise": "Squat", "reps": 5, "weight_kg": 90}]},
    )
    assert len(replaced.json()["sets"]) == 1
    assert client.get(f"/api/strength/sessions/{session_id}").json()["sets"][0]["reps"] == 5

    assert client.delete(f"/api/strength/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/strength/sessions/{session_id}").status_code == 404


def test_session_validation(client: TestClient) -> None:
    def post(**changes: object) -> int:
        return client.post("/api/strength/sessions", json={**SESSION, **changes}).status_code

    assert post(sets=[]) == 422
    assert post(sets=[{"exercise": "Squat", "reps": 0}]) == 422
    assert post(sets=[{"exercise": "Squat", "reps": 5, "weight_kg": 600}]) == 422
    assert post(sets=[{"exercise": "Squat", "reps": 5, "rpe": 11}]) == 422
    assert post(sets=[{"exercise": "   ", "reps": 5}]) == 422
    assert post(duration_min=0) == 422
    assert post(performed_at="2026-10-14T18:00:00") == 422  # no timezone
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    assert post(performed_at=future) == 422
    assert post(activity_id=999) == 422


def test_exercises_with_last_load(client: TestClient) -> None:
    client.post("/api/strength/sessions", json=SESSION)
    later = {
        "performed_at": "2026-10-16T18:00:00+02:00",
        "sets": [
            {"exercise": "Squat", "reps": 6, "weight_kg": 85},
            {"exercise": "Squat", "reps": 5, "weight_kg": 87.5},
            {"exercise": "Hack squat maison", "reps": 12, "weight_kg": 40},
        ],
    }
    client.post("/api/strength/sessions", json=later)

    exercises = {e["name"]: e for e in client.get("/api/strength/exercises").json()}
    assert len(exercises) >= 30
    assert exercises["Squat"]["last_weight_kg"] == 87.5  # last set of the last session
    assert exercises["Squat"]["last_reps"] == 5
    assert exercises["Développé couché"]["last_weight_kg"] == 60
    assert exercises["Hack squat maison"]["group"] == "Mes exercices"
    assert exercises["Pompes"]["bodyweight"] is True
    assert exercises["Pompes"]["last_reps"] is None


def test_activity_can_be_linked_once(client: TestClient, db: Session) -> None:
    activity = add_activity(db, "WeightTraining", datetime(2026, 10, 14, 16, 0, tzinfo=UTC))
    first = client.post("/api/strength/sessions", json={**SESSION, "activity_id": activity.id})
    assert first.status_code == 201
    second = client.post("/api/strength/sessions", json={**SESSION, "activity_id": activity.id})
    assert second.status_code == 409


def test_typed_session_alone_counts(client: TestClient, db: Session) -> None:
    strength = add_goal(db, "strength_sessions", 3)
    minutes = add_goal(db, "active_minutes", 150)
    client.post("/api/strength/sessions", json=SESSION)

    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    by_goal = {item["goal"]["id"]: item for item in body["goals"]}
    assert by_goal[strength.id]["done"] == 1
    assert by_goal[minutes.id]["done"] == 60
    assert body["sessions"][0]["counted"] is True
    assert body["sessions"][0]["exercises"] == ["Squat", "Développé couché", "Tractions"]
    assert body["sessions"][0]["set_count"] == 4


def test_session_recorded_on_strava_counts_once(client: TestClient, db: Session) -> None:
    strength = add_goal(db, "strength_sessions", 3)
    # The watch recorded the same gym session 20 minutes earlier (synced after typing).
    add_activity(db, "WeightTraining", datetime(2026, 10, 14, 15, 40, tzinfo=UTC))
    client.post("/api/strength/sessions", json=SESSION)

    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    assert body["goals"][0]["goal"]["id"] == strength.id
    assert body["goals"][0]["done"] == 1
    assert body["sessions"][0]["counted"] is False


def test_linked_session_counts_once_even_far_from_activity(client: TestClient, db: Session) -> None:
    add_goal(db, "strength_sessions", 3)
    activity = add_activity(db, "WeightTraining", datetime(2026, 10, 13, 8, 0, tzinfo=UTC))
    client.post("/api/strength/sessions", json={**SESSION, "activity_id": activity.id})

    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    assert body["goals"][0]["done"] == 1


def test_run_near_session_does_not_hide_it(client: TestClient, db: Session) -> None:
    add_goal(db, "strength_sessions", 3)
    add_activity(db, "Run", datetime(2026, 10, 14, 15, 0, tzinfo=UTC))
    client.post("/api/strength/sessions", json=SESSION)

    body = client.get("/api/goals/progress", params={"week": "2026-W42"}).json()
    assert body["goals"][0]["done"] == 1


def _two_strength_sessions(db: Session, monday: datetime) -> None:
    add_activity(db, "WeightTraining", monday + timedelta(hours=18))
    add_activity(db, "Workout", monday + timedelta(days=2, hours=18))


def test_history_and_streak(db: Session) -> None:
    add_goal(db, "strength_sessions", 2)
    weeks = ["2026-W39", "2026-W40", "2026-W41"]
    # W38 achieved, W39 missed, W40 and W41 achieved, W42 (current) not yet.
    for label in ["2026-W38", "2026-W40", "2026-W41"]:
        monday = parse_week(label).monday
        _two_strength_sessions(db, datetime(monday.year, monday.month, monday.day, tzinfo=UTC))
    db.add(StrengthSession(performed_at=datetime(2026, 9, 22, 17, 0, tzinfo=UTC), sets=[]))
    db.commit()

    current = parse_week("2026-W42")
    history = weeks_history(db, current, 5, "Europe/Luxembourg")
    assert [data.week.label for data in history] == ["2026-W38", *weeks, "2026-W42"]
    assert [data.progress[0].done for data in history] == [2, 1, 2, 2, 0]
    assert [data.all_achieved for data in history] == [True, False, True, True, False]
    # The unfinished current week does not break the streak.
    assert streak(history, current) == 2


def test_history_endpoint(client: TestClient, db: Session) -> None:
    add_goal(db, "cardio_sessions", 1)
    body = client.get("/api/goals/history", params={"weeks": 12}).json()
    assert len(body["weeks"]) == 12
    assert body["weeks"][-1]["goals"][0]["kind"] == "cardio_sessions"
    assert body["streak"] == 0
    assert client.get("/api/goals/history", params={"weeks": 60}).status_code == 422


def test_week_without_goals_breaks_streak(db: Session) -> None:
    history = weeks_history(db, parse_week("2026-W42"), 3, "Europe/Luxembourg")
    assert streak(history, parse_week("2026-W42")) == 0
