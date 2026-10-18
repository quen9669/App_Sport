"""Phase 5b: the longevity coach's tools, the weekly plan (tool, stream, routes).

The model is always the scripted FakeLLM.
"""

import json
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.coach import prompts
from app.coach.engine import Engine, PlanEvent, ToolEvent
from app.coach.tools import ALL_TOOLS, ToolContext, run_tool, tools_for
from app.config import Settings, get_settings
from app.db.models import Activity, CoachPlan, DailyHealth, SmokingDay
from app.repositories import coach as coach_repo
from app.services.weeks import current_week
from tests.fixtures.fake_llm import FakeLLM, text_turn, tool_turn
from tests.test_coach import NOW, PLAN, sse


def call(db: Session, name: str, arguments: dict[str, Any] | None = None) -> Any:
    context = ToolContext(db, get_settings(), "longevity", NOW)
    text, is_error = run_tool(ALL_TOOLS[name], context, arguments or {})
    return json.loads(text), is_error


# --- Which coach gets which tool ---------------------------------------------------


def test_each_coach_has_its_own_tools_and_prompt() -> None:
    training = {t.name for t in tools_for("training")}
    longevity = {t.name for t in tools_for("longevity")}
    assert "propose_weekly_plan" in training and "propose_weekly_plan" not in longevity
    assert "get_smoke_free" in longevity and "get_smoke_free" not in training
    assert {"get_daily_activity", "get_vo2max_trend", "get_sleep"} <= longevity
    prompt = prompts.system_prompt("longevity")
    assert prompt.version == "longevity-v1+common-v1"
    assert "bien établi" in prompt.text and "complément" in prompt.text


def test_plan_schema_is_flat_for_every_provider() -> None:
    schema = json.dumps(ALL_TOOLS["propose_weekly_plan"].schema())
    assert "$ref" not in schema and "$defs" not in schema
    assert '"kind"' in schema  # the session fields are inlined


# --- Longevity tools -------------------------------------------------------------


def test_daily_activity_has_steps_floors_and_intensity(db: Session) -> None:
    today = date(2026, 10, 18)
    for offset in range(3):
        db.add(
            DailyHealth(
                source="garmin",
                day=today - timedelta(days=offset),
                steps=9000 + 1000 * offset,
                floors_ascended=10,
                intensity_moderate_min=30,
                intensity_vigorous_min=10,
            )
        )
    db.commit()
    result, is_error = call(db, "get_daily_activity", {"weeks": 2})
    assert not is_error
    current = result["weeks"][-1]
    assert current["week"] == "2026-W42"
    assert (current["steps_per_day"], current["floors_climbed"]) == (10000, 30)
    assert current["intensity_minutes"] == 3 * (30 + 2 * 10)
    assert len(result["last_14_days_steps"]) == 3


def test_vo2max_trend_by_month(db: Session) -> None:
    db.add(DailyHealth(source="garmin", day=date(2026, 9, 10), vo2max=48.0))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 10), vo2max=49.0))
    db.add(DailyHealth(source="garmin", day=date(2026, 10, 15), vo2max=50.0))
    db.commit()
    result, _ = call(db, "get_vo2max_trend")
    assert result["latest"] == {"date": "2026-10-15", "vo2max": 50.0}
    assert result["monthly_average"] == {"2026-09": 48.0, "2026-10": 49.5}


def run(days_ago: int, average_hr: float | None, max_hr: float | None) -> Activity:
    return Activity(
        source="garmin",
        external_id=f"run-{days_ago}",
        name="Footing",
        sport_type="running",
        start_time=NOW - timedelta(days=days_ago, hours=2),
        elapsed_time_s=3000,
        moving_time_s=2950,
        distance_m=8000,
        average_heartrate=average_hr,
        max_heartrate=max_hr,
    )


def test_heart_rate_zones_from_average_heart_rate(db: Session) -> None:
    # Max HR 171 is observed from the runs themselves (no profile value).
    db.add(run(1, 115, 171))  # 67 % -> z2
    db.add(run(2, 150, 171))  # 88 % -> z4
    db.add(run(3, None, None))
    db.commit()
    result, _ = call(db, "get_heart_rate_zones", {"weeks": 1})
    week = result["minutes_per_week"]["2026-W42"]
    assert result["max_heartrate"] == 171
    assert (week["z2"], week["z4"], week["no_hr"]) == (49, 49, 49)
    assert "AVERAGE" in result["note"]


def test_smoke_free_counts_without_notes(db: Session) -> None:
    db.add(SmokingDay(day=date(2026, 10, 1), cigarettes=2, note="soirée privée"))
    db.commit()
    result, _ = call(db, "get_smoke_free")
    assert result["quit_date"] == "2026-09-01"
    assert result["days_with_cigarettes"] == 1
    assert result["current_streak_days"] == 17  # 2 Oct to 18 Oct
    assert "soirée" not in json.dumps(result)  # personal notes never go to the model


# --- The weekly plan tool ----------------------------------------------------------


def test_plan_is_stored_as_a_proposal(db: Session) -> None:
    result, is_error = call(db, "propose_weekly_plan", PLAN)
    assert not is_error and result["status"] == "proposed"
    plan = db.get(CoachPlan, result["plan_id"])
    assert plan is not None and plan.status == "proposed"
    assert [s["day"] for s in plan.days] == ["2026-10-19", "2026-10-20"]  # sorted


def test_invalid_plans_are_errors_for_the_model(db: Session) -> None:
    tuesday = {**PLAN, "week_start": "2026-10-20"}
    assert call(db, "propose_weekly_plan", tuesday)[1]
    outside = {**PLAN, "sessions": [{**PLAN["sessions"][0], "day": "2026-10-27"}]}
    assert call(db, "propose_weekly_plan", outside)[1]
    too_long = {**PLAN, "sessions": [{**PLAN["sessions"][0], "duration_min": 600}]}
    assert call(db, "propose_weekly_plan", too_long)[1]
    far, _ = call(db, "propose_weekly_plan", {**PLAN, "week_start": "2026-12-07"})
    assert "error" in far  # more than two weeks ahead


def test_engine_streams_the_plan_card(db: Session, settings: Settings) -> None:
    conversation = coach_repo.create_conversation(db, "training")
    db.commit()
    llm = FakeLLM([tool_turn(("propose_weekly_plan", PLAN)), text_turn("Voici ta semaine.")])
    events = list(Engine(db, settings, llm, NOW).answer(conversation, "Un plan ?"))
    plans = [e for e in events if isinstance(e, PlanEvent)]
    assert len(plans) == 1
    assert plans[0].plan["week_start"] == "2026-10-19"
    assert plans[0].plan["status"] == "proposed"
    assert any(isinstance(e, ToolEvent) and e.name == "propose_weekly_plan" for e in events)
    plan = db.get(CoachPlan, plans[0].plan["id"])
    assert plan is not None and plan.conversation_id == conversation.id


# --- Routes ------------------------------------------------------------------------


def test_plan_flow_through_the_api(client: TestClient, fake: FakeLLM, db: Session) -> None:
    monday = current_week("Europe/Luxembourg").monday
    plan = {**PLAN, "week_start": monday.isoformat()}
    plan["sessions"] = [{**s, "day": monday.isoformat()} for s in PLAN["sessions"]]
    conversation = client.post("/api/coach/training/conversations").json()
    fake.turns += [tool_turn(("propose_weekly_plan", plan)), text_turn("Voici.")]
    body = client.post(
        f"/api/coach/conversations/{conversation['id']}/messages", json={"text": "Plan ?"}
    ).text
    card = next(data for name, data in sse(body) if name == "plan")
    assert card["status"] == "proposed" and len(card["sessions"]) == 2

    # Reopened later: the card is attached to the coach's answer.
    detail = client.get(f"/api/coach/conversations/{conversation['id']}").json()
    assert detail["messages"][-1]["plans"][0]["id"] == card["id"]

    assert client.get("/api/coach/plans/current").json()["this_week"] is None
    accepted = client.patch(f"/api/coach/plans/{card['id']}", json={"accepted": True}).json()
    assert accepted["status"] == "accepted"
    assert client.get("/api/coach/plans/current").json()["this_week"]["id"] == card["id"]

    # A second accepted plan for the same week replaces the first one.
    fake.turns += [tool_turn(("propose_weekly_plan", plan)), text_turn("Modifié.")]
    body = client.post(
        f"/api/coach/conversations/{conversation['id']}/messages", json={"text": "Moins long"}
    ).text
    second = next(data for name, data in sse(body) if name == "plan")
    client.patch(f"/api/coach/plans/{second['id']}", json={"accepted": True})
    assert client.get("/api/coach/plans/current").json()["this_week"]["id"] == second["id"]
    first = db.get(CoachPlan, card["id"])
    db.refresh(first)
    assert first is not None and first.status == "replaced"

    # Deleting the conversation keeps the accepted plan on Accueil.
    client.delete(f"/api/coach/conversations/{conversation['id']}")
    assert client.get("/api/coach/plans/current").json()["this_week"]["id"] == second["id"]
    assert client.patch("/api/coach/plans/999", json={"accepted": True}).status_code == 404


def test_longevity_conversations_are_separate(client: TestClient) -> None:
    client.post("/api/coach/longevity/conversations")
    assert len(client.get("/api/coach/longevity/conversations").json()) == 1
    assert client.get("/api/coach/training/conversations").json() == []
    assert client.get("/api/coach/other/conversations").status_code == 422
