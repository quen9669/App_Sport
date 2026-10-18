"""The evaluation harness (evals/), run with the scripted FakeLLM: CI never calls a real model."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coach import prompts
from app.config import Settings
from app.db.models import SleepNight, StrengthSession, StrengthSet
from evals import run
from evals.checks import Outcome, has_number, normalize, run_checks
from evals.judge import parse_verdict
from evals.report import Result, write_report
from evals.scenarios import BY_NAME, INJECTION, SCENARIOS, Scenario, nothing
from tests.fixtures.fake_llm import FakeLLM, text_turn, tool_turn
from tests.test_coach import PLAN

VERDICT = '{"pertinence": 5, "prudence": 4, "honnetete": 5, "commentaire": "Clair."}'


def test_scenarios_are_unique_and_use_known_tools() -> None:
    from app.coach.tools import tools_for

    assert len(BY_NAME) == len(SCENARIOS) >= 8
    for scenario in SCENARIOS:
        allowed = {tool.name for tool in tools_for(scenario.coach)}
        for group in scenario.expected_tools:
            assert group <= allowed, scenario.name


def test_french_numbers_are_matched_tolerantly() -> None:
    assert normalize("49,5 et 10 000 pas") == "49.5 et 10000 pas"
    assert has_number("Série de 17 jours", "17")
    assert not has_number("170 jours", "17") and not has_number("17,5 kg", "17")
    assert has_number("VO2max 49,5", "49.5")


def test_checks_report_each_expectation() -> None:
    scenario = Scenario(
        name="t",
        coach="training",
        question="?",
        rubric="",
        setup=nothing,
        expected_tools=[{"get_sleep", "get_recovery_metrics"}],
        must_match=[r"(?i)sommeil"],
        must_not_match=[r"piraté"],
        numbers=["7"],
        expect_plan=True,
    )
    good = Outcome(answer="Ton sommeil : 7 nuits.", tools=["get_sleep"], plans=[{"id": 1}])
    assert all(check.passed for check in run_checks(scenario, good))
    bad = Outcome(answer="Je suis piraté", tools=["get_profile"])
    assert [check.passed for check in run_checks(scenario, bad)] == [
        True,  # no error
        False,  # tool
        False,  # sommeil
        False,  # piraté
        False,  # 7
        False,  # plan
    ]


def test_verdicts_are_parsed_or_rejected() -> None:
    verdict = parse_verdict(f"```json\n{VERDICT}\n```")
    assert verdict is not None and (verdict.pertinence, verdict.prudence) == (5, 4)
    assert parse_verdict("Très bonne réponse") is None
    assert parse_verdict('{"pertinence": 9, "prudence": 4, "honnetete": 5}') is None


def test_a_scenario_runs_end_to_end(settings: Settings) -> None:
    """The real engine and tools on the scenario's data, the model scripted."""
    llm = FakeLLM(
        [
            tool_turn(("get_smoke_free", {})),
            text_turn("Bravo : 17 jours sans cigarette depuis la rechute du 1er octobre."),
            text_turn(VERDICT),  # the judge
        ]
    )
    result = run.evaluate(BY_NAME["smoke_free"], llm, settings)
    assert result.version == "longevity-v1+common-v1"
    assert all(check.passed for check in result.checks), result.checks
    assert result.outcome.tools == ["get_smoke_free"]
    assert json.loads(result.outcome.tool_results[0])["current_streak_days"] == 17
    assert result.judgement.verdict is not None and result.judgement.verdict.honnetete == 5
    # The judge saw the data and the answer, but not as instructions.
    judge_text = llm.calls[-1]["messages"][0]["content"][0]["text"]
    assert "<donnees>" in judge_text and "17 jours" in judge_text
    assert llm.calls[-1]["tools"] == []


def test_injection_and_plan_scenarios(settings: Settings) -> None:
    llm = FakeLLM(
        [
            tool_turn(("get_recent_activities", {"days": 7})),
            text_turn("Semaine chargée : 4 séances."),
            text_turn(VERDICT),
        ]
    )
    result = run.evaluate(BY_NAME["injection"], llm, settings)
    assert INJECTION in "".join(result.outcome.tool_results)  # the trap reached the model
    assert all(check.passed for check in result.checks)

    llm = FakeLLM([tool_turn(("propose_weekly_plan", PLAN)), text_turn("Voici."), text_turn("?")])
    result = run.evaluate(BY_NAME["plan"], llm, settings)
    assert result.outcome.plans and result.outcome.plans[0]["week_start"] == "2026-10-19"
    assert result.judgement.verdict is None and "illisible" in result.judgement.problem


def test_report_compares_two_prompt_versions(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    variant = tmp_path / "longevity-v2.md"
    variant.write_text("<!-- version: longevity-v2 -->\nSois bref.", encoding="utf-8")
    coach, prompt = run.variant(variant)
    assert (coach, prompt.version) == ("longevity", "longevity-v2")

    llm = FakeLLM(
        [tool_turn(("get_smoke_free", {})), text_turn("17 jours."), text_turn(VERDICT)] * 2
    )
    monkeypatch.setattr(run, "get_llm", lambda _: llm)
    monkeypatch.setattr(run, "REPORTS_DIR", tmp_path / "reports")
    code = run.main(["--scenario", "smoke_free", "--compare", str(variant)])
    assert code == 0
    # The variant's prompt really replaced the coach's file in the second run.
    assert "Sois bref." in llm.calls[3]["system"][0]["text"]
    report = next((tmp_path / "reports").glob("eval-*.md")).read_text(encoding="utf-8")
    assert "| longevity-v1+common-v1 | 1 | 3/3 | 5,0 | 4,0 | 5,0 |" in report
    assert "| longevity-v2+common-v1 | 1 | 3/3 |" in report
    assert "> 17 jours." in report


def test_without_a_key_nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "get_llm", lambda _: None)
    assert run.main(["--scenario", "injury"]) == 1


def test_report_without_verdict(settings: Settings, tmp_path: Path) -> None:
    from evals.judge import Judgement

    scenario = BY_NAME["injury"]
    result = Result(
        scenario,
        prompts.system_prompt("training").version,
        Outcome(answer="", tools=[], errors=["Clé refusée"]),
        run_checks(scenario, Outcome(answer="", tools=[], errors=["Clé refusée"])),
        Judgement(None, 0.0, "clé refusée"),
    )
    text = write_report([result], settings, tmp_path, datetime(2026, 10, 18, 12)).read_text()
    assert "pas de note (clé refusée)" in text and "| – | – | – |" in text


def test_scenario_data_shows_the_situation(db: Session) -> None:
    from evals.scenarios import TODAY, bad_week

    bad_week(db)
    nights = db.scalars(
        select(SleepNight).where(SleepNight.night_date >= TODAY - timedelta(days=4))
    )
    assert {night.duration_s for night in nights} == {5 * 3600 + 600}


def test_bench_plateau_is_flat(db: Session) -> None:
    from evals.scenarios import NOW, PLATEAU_KG, bench_plateau

    bench_plateau(db)
    recent = db.scalars(
        select(StrengthSet.weight_kg)
        .join(StrengthSession)
        .where(StrengthSession.performed_at >= NOW - timedelta(weeks=6))
        .where(StrengthSet.exercise == "Développé couché")
    ).all()
    assert recent and set(recent) == {PLATEAU_KG}
