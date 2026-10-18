"""Structured runs of the weekly plan and sending them to Garmin Connect.

Garmin is never called: a fake records what the app would send.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.plan_workouts import get_garmin_workout_login
from app.coach.tools import ALL_TOOLS, ToolContext, run_tool
from app.coach.tools.plan import PlanSession
from app.config import Settings
from app.db.models import CoachPlan
from app.dependencies import get_now
from app.integrations.health import garmin_workouts
from app.integrations.health.provider import HealthProviderError
from app.repositories import coach as coach_repo
from app.services.race.daniels import PaceZone
from app.services.workouts import RunWorkout, estimated_duration_s, garmin_payload, pace_targets
from tests.test_coach import NOW, add_run

# 15 min easy, 6 × 800 m at interval pace with 2 min jog, 10 min easy.
INTERVALS: dict[str, Any] = {
    "warmup": {"duration_s": 900, "pace": "easy"},
    "blocks": [
        {
            "repeats": 6,
            "work": {"distance_m": 800, "pace": "interval"},
            "recovery": {"duration_s": 120, "pace": "none"},
        }
    ],
    "cooldown": {"duration_s": 600, "pace": "easy"},
}
ZONES = [PaceZone("easy", 330.0, 300.0), PaceZone("interval", 240.0, 240.0)]


# --- Steps and paces ------------------------------------------------------------------


def test_single_paces_get_a_small_range() -> None:
    assert pace_targets(ZONES) == {"easy": (330, 300), "interval": (245, 235)}
    assert pace_targets([]) == {}


def test_a_step_has_a_duration_or_a_distance() -> None:
    with pytest.raises(ValidationError):
        RunWorkout.model_validate({"blocks": [{"work": {"pace": "easy"}}]})
    with pytest.raises(ValidationError):
        RunWorkout.model_validate(
            {"blocks": [{"work": {"duration_s": 600, "distance_m": 2000, "pace": "easy"}}]}
        )


def test_garmin_payload_of_an_interval_session() -> None:
    workout = RunWorkout.model_validate(INTERVALS)
    payload = garmin_payload("Fractionné", workout, pace_targets(ZONES), "6 × 800 m")
    steps = payload["workoutSegments"][0]["workoutSteps"]
    assert payload["sportType"]["sportTypeKey"] == "running"
    assert [s["type"] for s in steps] == [
        "ExecutableStepDTO",
        "RepeatGroupDTO",
        "ExecutableStepDTO",
    ]
    warmup, repeat, cooldown = steps
    assert warmup["stepType"]["stepTypeKey"] == "warmup" and warmup["endConditionValue"] == 900
    # The slow end of the range is the low speed, in m/s.
    assert warmup["targetType"]["workoutTargetTypeKey"] == "pace.zone"
    assert warmup["targetValueOne"] == round(1000 / 330, 4)
    assert warmup["targetValueTwo"] == round(1000 / 300, 4)
    assert repeat["numberOfIterations"] == 6
    work, recovery = repeat["workoutSteps"]
    assert work["endCondition"]["conditionTypeKey"] == "distance"
    assert work["endConditionValue"] == 800
    assert work["targetValueOne"] == round(1000 / 245, 4)
    assert recovery["targetType"]["workoutTargetTypeKey"] == "no.target"
    assert cooldown["stepType"]["stepTypeKey"] == "cooldown"
    # Steps are numbered in order, the repeat group included.
    assert [warmup["stepOrder"], repeat["stepOrder"], work["stepOrder"]] == [1, 2, 3]
    assert [recovery["stepOrder"], cooldown["stepOrder"]] == [4, 5]


def test_without_form_the_steps_have_no_pace_target() -> None:
    payload = garmin_payload("Footing", RunWorkout.model_validate(INTERVALS), {})
    steps = payload["workoutSegments"][0]["workoutSteps"]
    assert all(s.get("targetType", {}).get("workoutTargetTypeKey") != "pace.zone" for s in steps)


def test_estimated_duration_uses_the_middle_pace() -> None:
    workout = RunWorkout.model_validate(INTERVALS)
    # 900 + 600 + 6 × (0.8 km × 240 s + 120 s)
    assert estimated_duration_s(workout, pace_targets(ZONES)) == 900 + 600 + 6 * (192 + 120)


# --- The coach's tool -----------------------------------------------------------------


def _plan_args(workout: dict[str, Any] | None, kind: str = "run") -> dict[str, Any]:
    session: dict[str, Any] = {
        "day": "2026-10-20",
        "kind": kind,
        "title": "Fractionné",
        "duration_min": 50,
        "why": "VMA",
    }
    if workout is not None:
        session["workout"] = workout
    return {"week_start": "2026-10-19", "summary": "Une semaine.", "sessions": [session]}


def test_the_coach_can_attach_steps_to_runs_only(db: Session, settings: Settings) -> None:
    context = ToolContext(db, settings, "training", NOW)
    tool = ALL_TOOLS["propose_weekly_plan"]
    text, is_error = run_tool(tool, context, _plan_args(INTERVALS))
    assert not is_error
    plan = db.get(CoachPlan, json.loads(text)["plan_id"])
    assert plan is not None and plan.days[0]["workout"]["blocks"][0]["repeats"] == 6
    _, is_error = run_tool(tool, context, _plan_args(INTERVALS, kind="ride"))
    assert is_error
    schema = json.dumps(tool.schema())
    assert '"blocks"' in schema and "$ref" not in schema


# --- Garmin calls ---------------------------------------------------------------------


class FakeGarmin:
    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, Any]] = []

    def _record(self, name: str, value: Any) -> None:
        self.calls.append((name, value))
        if self.fail == name:
            raise RuntimeError("boom")  # call_garmin turns it into HealthProviderError

    def upload_workout(self, workout_json: dict[str, Any]) -> dict[str, Any]:
        self._record("upload", workout_json)
        return {"workoutId": 77}

    def schedule_workout(self, workout_id: int | str, date_str: str) -> dict[str, Any]:
        self._record("schedule", (workout_id, date_str))
        return {"workoutScheduleId": 88}

    def unschedule_workout(self, scheduled_workout_id: int | str) -> Any:
        self._record("unschedule", scheduled_workout_id)

    def delete_workout(self, workout_id: int | str) -> Any:
        self._record("delete", workout_id)


def test_a_failed_schedule_deletes_the_new_workout() -> None:
    api = FakeGarmin(fail="schedule")
    with pytest.raises(HealthProviderError):
        garmin_workouts.create_and_schedule(api, {}, "2026-10-20")
    assert [name for name, _ in api.calls] == ["upload", "schedule", "delete"]


def test_remove_deletes_only_what_the_app_created() -> None:
    api = FakeGarmin()
    garmin_workouts.remove(api, 77, 88)
    assert api.calls == [("unschedule", 88), ("delete", 77)]


# --- Routes ---------------------------------------------------------------------------


def _accepted_plan(db: Session) -> CoachPlan:
    # Stored as the tool stores them: every field, through the tool's own model.
    raw = [
        _plan_args(INTERVALS)["sessions"][0],
        {
            "day": "2026-10-21",
            "kind": "strength",
            "title": "Muscu",
            "duration_min": 60,
            "why": "Force",
        },
    ]
    sessions = [PlanSession.model_validate(s).model_dump(mode="json") for s in raw]
    plan = coach_repo.propose_plan(db, "training", None, NOW.date(), "Semaine", sessions)
    coach_repo.decide_plan(db, plan, True)
    db.commit()
    return plan


@pytest.fixture
def garmin(client: TestClient) -> FakeGarmin:
    api = FakeGarmin()
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_garmin_workout_login] = lambda: lambda: api
    overrides[get_now] = lambda: NOW
    return api


def test_send_and_remove_a_run(client: TestClient, db: Session, garmin: FakeGarmin) -> None:
    for days_ago in (3, 10, 20):  # enough runs for a form, hence real paces
        add_run(db, days_ago)
    plan = _accepted_plan(db)
    url = f"/api/coach/plans/{plan.id}/sessions/0"

    sent = client.post(f"{url}/garmin")
    assert sent.status_code == 200
    assert sent.json()["sessions"][0]["garmin"]["workout_id"] == 77
    payload = garmin.calls[0][1]
    interval = payload["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["targetType"]["workoutTargetTypeKey"] == "pace.zone"
    assert garmin.calls[1] == ("schedule", (77, "2026-10-20"))

    # Already sent: no double, and no edit until it is taken back.
    assert client.post(f"{url}/garmin").status_code == 409
    assert client.put(f"{url}/workout", json=INTERVALS).status_code == 409

    removed = client.delete(f"{url}/garmin")
    assert removed.status_code == 200 and removed.json()["sessions"][0]["garmin"] is None
    assert garmin.calls[-2:] == [("unschedule", 88), ("delete", 77)]

    edited = {**INTERVALS, "blocks": [{"repeats": 5, "work": {"distance_m": 1000}}]}
    saved = client.put(f"{url}/workout", json=edited)
    assert saved.json()["sessions"][0]["workout"]["blocks"][0]["repeats"] == 5


def test_what_cannot_be_sent(client: TestClient, db: Session, garmin: FakeGarmin) -> None:
    plan = _accepted_plan(db)
    base = f"/api/coach/plans/{plan.id}/sessions"
    assert client.post(f"{base}/1/garmin").status_code == 409  # strength, no steps
    assert client.post(f"{base}/9/garmin").status_code == 409  # no such session
    assert client.post("/api/coach/plans/999/sessions/0/garmin").status_code == 404
    assert client.delete(f"{base}/0/garmin").status_code == 409  # not sent yet

    proposed = coach_repo.propose_plan(db, "training", None, NOW.date(), "S", plan.days)
    db.commit()
    assert client.post(f"/api/coach/plans/{proposed.id}/sessions/0/garmin").status_code == 409

    past = coach_repo.propose_plan(
        db, "training", None, NOW.date(), "S", [{**plan.days[0], "day": "2026-10-17"}]
    )
    coach_repo.decide_plan(db, past, True)
    db.commit()
    assert client.post(f"/api/coach/plans/{past.id}/sessions/0/garmin").status_code == 409
    assert garmin.calls == []


def test_garmin_missing_or_broken(client: TestClient, db: Session, garmin: FakeGarmin) -> None:
    plan = _accepted_plan(db)
    url = f"/api/coach/plans/{plan.id}/sessions/0/garmin"
    garmin.fail = "upload"
    assert client.post(url).status_code == 502
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_garmin_workout_login] = lambda: None
    answer = client.post(url)
    assert answer.status_code == 409 and "Sources" in answer.json()["detail"]


def test_current_plans_carry_the_paces(client: TestClient, db: Session) -> None:
    client.app.dependency_overrides[get_now] = lambda: NOW  # type: ignore[attr-defined]
    assert client.get("/api/coach/plans/current").json()["pace_targets"] == {}
    for days_ago in (3, 10, 20):
        add_run(db, days_ago)
    targets = client.get("/api/coach/plans/current").json()["pace_targets"]
    assert set(targets) == {"easy", "marathon", "threshold", "interval", "repetition"}
    assert targets["interval"]["slow_s_per_km"] > targets["interval"]["fast_s_per_km"]
