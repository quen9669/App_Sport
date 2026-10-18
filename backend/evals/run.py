"""Run the evaluation: ``make eval`` (or ``make eval ARGS="--scenario injury"``).

Each scenario gets its own empty in-memory database, filled with synthetic data,
then the real coach engine answers the question with the real model (the one
chosen in .env), the checks run and the judge grades the answer.

To compare a new version of a prompt with the current one, copy the file,
change it (and its version line), then:

    make eval ARGS="--compare path/to/training-v3.md"

The scenarios of that coach run twice, once per version, side by side in the
report (evals/reports/, not committed). The calls cost real money but are not
counted in the coach's monthly budget (they are logged in the throwaway
database): ``--max-eur`` stops the run once that much has been spent.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (registers the tables)
from app.api.coach import get_llm
from app.coach import prompts
from app.coach.engine import DoneEvent, Engine, ErrorEvent, PlanEvent, TextEvent, ToolEvent
from app.coach.llm import LLM
from app.config import Settings, get_settings
from app.db.base import Base
from app.repositories import coach as coach_repo
from evals.checks import Outcome, run_checks
from evals.judge import judge
from evals.report import Result, write_report
from evals.scenarios import BY_NAME, NOW, SCENARIOS, Scenario

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def run_scenario(
    scenario: Scenario, llm: LLM, settings: Settings, prompt: prompts.Prompt | None = None
) -> Outcome:
    """One answer of the coach, on a fresh database prepared by the scenario."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            scenario.setup(db)
            conversation = coach_repo.create_conversation(db, scenario.coach)
            db.commit()
            outcome = Outcome(answer="", tools=[])
            coach = Engine(db, settings, llm, NOW, prompt)
            for event in coach.answer(conversation, scenario.question):
                if isinstance(event, TextEvent):
                    outcome.answer += event.text
                elif isinstance(event, ToolEvent):
                    outcome.tools.append(event.name)
                elif isinstance(event, PlanEvent):
                    outcome.plans.append(event.plan)
                elif isinstance(event, ErrorEvent):
                    outcome.errors.append(event.message)
                elif isinstance(event, DoneEvent):
                    outcome.cost_eur = event.cost_eur
            outcome.tool_results = [
                str(block.get("content"))
                for message in conversation.messages
                for block in message.content
                if block.get("type") == "tool_result"
            ]
            return outcome
    finally:
        engine.dispose()


def evaluate(
    scenario: Scenario, llm: LLM, settings: Settings, prompt: prompts.Prompt | None = None
) -> Result:
    version = prompts.system_prompt(scenario.coach, prompt).version
    outcome = run_scenario(scenario, llm, settings, prompt)
    checks = run_checks(scenario, outcome)
    judgement = judge(llm, settings, scenario, outcome)
    return Result(scenario, version, outcome, checks, judgement)


def variant(path: Path) -> tuple[str, prompts.Prompt]:
    """A prompt file to compare: its coach comes from its version ("training-v3")."""
    prompt = prompts.parse(path.read_text(encoding="utf-8"), str(path))
    coach = prompt.version.split("-v")[0]
    if coach not in {"training", "longevity"}:
        raise SystemExit(f"{path}: the version must start with training- or longevity-")
    return coach, prompt


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Évaluation des coachs IA (appels réels payants)")
    parser.add_argument("--scenario", action="append", choices=sorted(BY_NAME), help="un seul")
    parser.add_argument("--compare", type=Path, help="autre version d'un prompt à comparer")
    parser.add_argument("--max-eur", type=float, default=2.0, help="arrêt au-delà (défaut 2 €)")
    parser.add_argument("--list", action="store_true", help="liste les scénarios et s'arrête")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        for scenario in SCENARIOS:
            print(f"{scenario.name:14} {scenario.coach:10} {scenario.question}")
        return 0
    settings = get_settings()
    llm = get_llm(settings)
    if llm is None:
        print("Aucune clé API dans .env (GEMINI_API_KEY ou ANTHROPIC_API_KEY) : rien à évaluer.")
        return 1
    scenarios = [BY_NAME[name] for name in args.scenario] if args.scenario else SCENARIOS
    runs: list[tuple[Scenario, prompts.Prompt | None]] = [(s, None) for s in scenarios]
    if args.compare:
        coach, other = variant(args.compare)
        runs += [(s, other) for s in scenarios if s.coach == coach]

    results: list[Result] = []
    spent = 0.0
    for scenario, prompt in runs:
        if spent >= args.max_eur:
            print(f"Arrêt : {spent:.2f} € dépensés (limite --max-eur {args.max_eur:.2f} €).")
            break
        result = evaluate(scenario, llm, settings, prompt)
        spent += result.cost_eur
        passed = sum(check.passed for check in result.checks)
        print(f"{scenario.name:14} {result.version:28} {passed}/{len(result.checks)} contrôles")
        results.append(result)

    path = write_report(results, settings, REPORTS_DIR, datetime.now())
    print(f"Rapport : {path}  (coût total {spent:.2f} €)")
    return 0 if all(check.passed for r in results for check in r.checks) else 1


if __name__ == "__main__":
    sys.exit(main())
