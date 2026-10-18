"""The evaluation report: one Markdown file, in French, readable on GitHub or in VS Code.

At the top, one line per prompt version (checks passed, the judge's average
grades, cost), so two versions can be compared at a glance; below, each
scenario with its checks, grades and the full answer.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

from app.config import Settings
from evals.checks import Check, Outcome
from evals.judge import Judgement
from evals.scenarios import Scenario

CRITERIA = ["pertinence", "prudence", "honnetete"]


@dataclass(frozen=True)
class Result:
    scenario: Scenario
    version: str  # prompt version, e.g. "training-v2+common-v1"
    outcome: Outcome
    checks: list[Check]
    judgement: Judgement

    @property
    def cost_eur(self) -> float:
        return self.outcome.cost_eur + self.judgement.cost_eur


def _average(results: list[Result], criterion: str) -> str:
    grades = [getattr(r.judgement.verdict, criterion) for r in results if r.judgement.verdict]
    return f"{mean(grades):.1f}".replace(".", ",") if grades else "–"


def _euros(value: float) -> str:
    return f"{value:.3f} €".replace(".", ",")


def summary(results: list[Result]) -> list[str]:
    lines = [
        "| Version du prompt | Scénarios | Contrôles réussis | Pertinence | Prudence "
        "| Honnêteté | Coût |",
        "|---|---|---|---|---|---|---|",
    ]
    for version in dict.fromkeys(r.version for r in results):  # keeps the run order
        group = [r for r in results if r.version == version]
        passed = sum(c.passed for r in group for c in r.checks)
        total = sum(len(r.checks) for r in group)
        grades = " | ".join(_average(group, criterion) for criterion in CRITERIA)
        cost = _euros(sum(r.cost_eur for r in group))
        lines.append(f"| {version} | {len(group)} | {passed}/{total} | {grades} | {cost} |")
    return lines


def section(result: Result) -> list[str]:
    outcome, verdict = result.outcome, result.judgement.verdict
    lines = [f"### {result.scenario.name} · {result.version}", ""]
    lines += [f"- {'✅' if check.passed else '❌'} {check.label}" for check in result.checks]
    lines.append(f"- Outils : {', '.join(outcome.tools) or 'aucun'}")
    if verdict:
        grades = ", ".join(f"{c} {getattr(verdict, c)}/5" for c in CRITERIA)
        lines.append(f"- Juge : {grades}. {verdict.commentaire}")
    else:
        lines.append(f"- Juge : pas de note ({result.judgement.problem})")
    lines.append(f"- Coût : {_euros(result.cost_eur)}")
    if outcome.errors:
        lines.append(f"- Erreur : {' / '.join(outcome.errors)}")
    answer = outcome.answer.strip() or "(pas de réponse)"
    lines += ["", *(f"> {line}" for line in answer.splitlines()), ""]
    return lines


def render(results: list[Result], settings: Settings, when: datetime) -> str:
    lines = [
        f"# Évaluation des coachs, {when:%Y-%m-%d %H:%M}",
        "",
        f"Modèle : {settings.main_model} (le juge utilise le même). "
        "Données synthétiques uniquement.",
        "",
        *summary(results),
        "",
    ]
    for scenario in dict.fromkeys(r.scenario.name for r in results):
        first = next(r for r in results if r.scenario.name == scenario)
        lines += [
            f"## {scenario} ({first.scenario.coach})",
            "",
            f"**Question** : {first.scenario.question}",
            "",
        ]
        for result in results:
            if result.scenario.name == scenario:
                lines += section(result)
    return "\n".join(lines)


def write_report(results: list[Result], settings: Settings, folder: Path, when: datetime) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"eval-{when:%Y-%m-%d-%H%M%S}.md"
    path.write_text(render(results, settings, when), encoding="utf-8")
    return path
