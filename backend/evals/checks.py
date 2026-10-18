"""Automatic checks of one answer: pure functions, no model and no database.

They catch the clear failures (a tool not used, a number missing, a forbidden
phrase); what needs judgement (is the advice good?) is left to the judge.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from evals.scenarios import Scenario


@dataclass(frozen=True)
class Check:
    label: str  # French, shown in the report
    passed: bool


@dataclass
class Outcome:
    """What the coach did for one scenario."""

    answer: str  # the text shown to FRANKS
    tools: list[str]  # tools run, in order
    tool_results: list[str] = field(default_factory=list)  # what the model read (for the judge)
    plans: list[dict[str, Any]] = field(default_factory=list)  # plan cards proposed
    errors: list[str] = field(default_factory=list)
    cost_eur: float = 0.0


def normalize(text: str) -> str:
    """French numbers to plain ones: "49,5" -> "49.5", "10 000" -> "10000"."""
    text = re.sub(r"(?<=\d)[\s  ](?=\d{3}\b)", "", text)  # thousands separators
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


def has_number(answer: str, number: str) -> bool:
    """True if ``number`` appears as a whole number: "17" is in "17 jours", not in "170"."""
    wanted = re.escape(normalize(number))
    return re.search(rf"(?<![\d.]){wanted}(?![\d]|\.\d)", normalize(answer)) is not None


def run_checks(scenario: Scenario, outcome: Outcome) -> list[Check]:
    checks = [Check("Pas d'erreur", not outcome.errors and bool(outcome.answer.strip()))]
    used = set(outcome.tools)
    for group in scenario.expected_tools:
        checks.append(Check(f"Outil utilisé : {' ou '.join(sorted(group))}", bool(group & used)))
    for pattern in scenario.must_match:
        found = re.search(pattern, outcome.answer, re.MULTILINE) is not None
        checks.append(Check(f"Contient /{pattern}/", found))
    for pattern in scenario.must_not_match:
        found = re.search(pattern, outcome.answer, re.MULTILINE) is not None
        checks.append(Check(f"Ne contient pas /{pattern}/", not found))
    for number in scenario.numbers:
        checks.append(Check(f"Donne le chiffre {number}", has_number(outcome.answer, number)))
    if scenario.expect_plan:
        # The tool validated the plan (Pydantic) before storing it: one card is enough.
        checks.append(Check("Plan de semaine valide proposé", bool(outcome.plans)))
        runs = [s for plan in outcome.plans for s in plan.get("sessions", []) if s["kind"] == "run"]
        if runs:
            # Every run must carry its steps, so FRANKS can send it to his watch.
            structured = all(run.get("workout") for run in runs)
            checks.append(Check("Séances de course détaillées en étapes", structured))
    return checks
