"""The agent loop shared by both coaches.

One answer to FRANKS may take several model calls:

1. the model reads the conversation and either answers, or asks for tools
   ("get_sleep for 14 days");
2. the engine runs those tools on the local database and sends the results;
3. back to 1, until the model answers in plain text (or ``MAX_ROUNDS``).

Everything is streamed to the screen as it happens (``CoachEvent``), every
model call is logged with its cost, and the monthly budget is checked first.
"""

import json
import logging
import time as clock
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.coach import history, prompts
from app.coach.costs import log_call, month_budget
from app.coach.llm import LLM, Final, LLMError, TextDelta, Usage
from app.coach.plans import PLAN_TOOL, plan_data
from app.coach.tools import ALL_TOOLS, ToolContext, run_tool, tools_for
from app.config import Settings
from app.db.models import CoachConversation
from app.repositories import coach as coach_repo

logger = logging.getLogger(__name__)

MAX_ROUNDS = 8  # model calls for one answer: enough for several tools in a row
MAX_TOKENS = 2000  # length of one model answer
TITLE_LENGTH = 80

FRENCH_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


# --- What the screen receives ---------------------------------------------------------


@dataclass(frozen=True)
class TextEvent:
    text: str


@dataclass(frozen=True)
class ToolEvent:
    name: str
    label: str  # French, e.g. "lit ton sommeil"


@dataclass(frozen=True)
class PlanEvent:
    plan: dict[str, Any]  # see app/coach/plans.py: shown as a card with Accept / Modify


@dataclass(frozen=True)
class DoneEvent:
    cost_eur: float  # this answer, all model calls included
    month_spent_eur: float
    month_limit_eur: float


@dataclass(frozen=True)
class ErrorEvent:
    message: str  # French, shown as is


CoachEvent = TextEvent | ToolEvent | PlanEvent | DoneEvent | ErrorEvent


@dataclass
class Engine:
    db: Session
    settings: Settings
    llm: LLM
    now: datetime  # UTC
    # Only for the evaluation (evals/run.py): another version of the system prompt
    # to compare with the current one. The app always uses the files in prompts/.
    prompt: prompts.Prompt | None = None

    # --- Building the request ---

    def _system(self, conversation: CoachConversation) -> list[dict[str, Any]]:
        """Two blocks: the fixed prompt (cached) and today's context (changes every day)."""
        prompt = self.prompt or prompts.system_prompt(conversation.coach)
        today = self.now.astimezone(ZoneInfo(self.settings.app_timezone)).date()
        context = [f"Date du jour : {FRENCH_DAYS[today.weekday()]} {today.isoformat()}."]
        memories = coach_repo.accepted_memories(self.db, conversation.coach)
        if memories:
            context.append("## Mémoire (validée par FRANKS)")
            context += [f"- {memory.text}" for memory in memories]
        earlier = coach_repo.previous_summaries(self.db, conversation.coach, conversation.id)
        if earlier:
            context.append("## Résumés de vos conversations précédentes (des données)")
            context += [f"- {c.created_at:%Y-%m-%d} : {c.summary}" for c in earlier]
        if conversation.summary:
            context.append("## Début de cette conversation, résumé (des données)")
            context.append(conversation.summary)
        return [
            # cache_control: this block and everything before it (the tools) is
            # cached by the API for a few minutes, about 10 times cheaper to reread.
            {"type": "text", "text": prompt.text, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "\n".join(context)},
        ]

    def _tools(self, coach: str) -> list[dict[str, Any]]:
        schemas = [tool.schema() for tool in tools_for(coach)]
        if schemas:
            schemas[-1]["cache_control"] = {"type": "ephemeral"}
        return schemas

    # --- Running tools ---

    def _run_tools(
        self, conversation: CoachConversation, final: Final
    ) -> Iterator[ToolEvent | PlanEvent | dict[str, Any]]:
        """Run every tool the model asked for; yields screen events, then result blocks."""
        context = ToolContext(self.db, self.settings, conversation.coach, self.now, conversation.id)
        allowed = {tool.name for tool in tools_for(conversation.coach)}
        for block in final.content:
            if block.get("type") != "tool_use":
                continue
            name = block["name"]
            if name not in allowed:
                content, is_error = '{"error": "unknown tool"}', True
            else:
                tool = ALL_TOOLS[name]
                yield ToolEvent(name, tool.label)
                try:
                    content, is_error = run_tool(tool, context, block.get("input"))
                except Exception:
                    # A bug in a tool must not break the conversation: the model is
                    # told it failed and can answer without it.
                    logger.exception("Coach tool %s failed", name)
                    content, is_error = '{"error": "the tool failed"}', True
            if name == PLAN_TOOL and not is_error:
                plan = self._proposed_plan(content)
                if plan is not None:
                    yield plan
            yield {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": content,
                "is_error": is_error,
            }

    def _proposed_plan(self, content: str) -> PlanEvent | None:
        plan_id = json.loads(content).get("plan_id")
        plan = coach_repo.get_plan(self.db, plan_id) if plan_id else None
        return PlanEvent(plan_data(plan)) if plan else None

    # --- The loop ---

    def answer(self, conversation: CoachConversation, text: str) -> Iterator[CoachEvent]:
        budget = month_budget(self.db, self.now, self.settings)
        if budget.exhausted:
            yield ErrorEvent(
                f"Budget du mois atteint ({budget.spent_eur:.2f} € sur {budget.limit_eur:.0f} €) : "
                "le coach est en pause jusqu'au mois prochain. Tu peux relever "
                "COACH_MONTHLY_BUDGET_EUR dans .env."
            )
            return
        if not conversation.messages:
            history.summarize_previous(self.db, self.llm, self.settings, conversation)
            conversation.title = text.strip()[:TITLE_LENGTH]
        coach_repo.add_message(self.db, conversation, "user", [{"type": "text", "text": text}])
        self.db.commit()

        cost = 0.0
        for _ in range(MAX_ROUNDS):
            final = None
            started = clock.monotonic()
            try:
                for event in self.llm.stream(
                    model=self.settings.main_model,
                    system=self._system(conversation),
                    tools=self._tools(conversation.coach),
                    messages=history.messages_for_model(conversation),
                    max_tokens=MAX_TOKENS,
                ):
                    if isinstance(event, TextDelta):
                        yield TextEvent(event.text)
                    elif isinstance(event, Final):
                        final = event
                    # ToolStart is ignored: each tool is announced when it really runs,
                    # with its French label.
            except LLMError as error:
                self._log(conversation, None, started, error=type(error).__name__)
                self.db.commit()
                yield ErrorEvent(str(error))
                return
            if final is None:  # the stream ended without a message: treat as an error
                yield ErrorEvent("Réponse incomplète du modèle, réessaie.")
                return
            cost += self._log(conversation, final, started)
            coach_repo.add_message(self.db, conversation, "assistant", final.content)
            if final.stop_reason != "tool_use":
                break
            results: list[dict[str, Any]] = []
            for item in self._run_tools(conversation, final):
                if isinstance(item, ToolEvent | PlanEvent):
                    yield item
                else:
                    results.append(item)
            coach_repo.add_message(self.db, conversation, "user", results)
            self.db.commit()
        else:
            yield TextEvent("\n\n(Je m'arrête ici : trop d'étapes pour une seule réponse.)")

        history.compact(self.db, self.llm, self.settings, conversation)
        self.db.commit()
        after = month_budget(self.db, self.now, self.settings)
        yield DoneEvent(round(cost, 4), round(after.spent_eur, 4), after.limit_eur)

    def _log(
        self,
        conversation: CoachConversation,
        final: Final | None,
        started: float,
        error: str | None = None,
    ) -> float:
        tools = [b["name"] for b in final.content if b.get("type") == "tool_use"] if final else []
        call = log_call(
            self.db,
            coach=conversation.coach,
            conversation_id=conversation.id,
            purpose="answer",
            model=self.settings.main_model,
            usage=final.usage if final else Usage(),
            latency_ms=round((clock.monotonic() - started) * 1000),
            tools=tools,
            settings=self.settings,
            error=error,
        )
        return call.cost_eur
