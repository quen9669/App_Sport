"""Coach routes: status and budget, conversations, the streamed answer, memories.

The answer is streamed with Server-Sent Events (SSE): one HTTP response that
stays open and receives small ``event: ... / data: {...}`` messages as the
coach writes, so the text appears word by word on screen.
"""

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from app.coach.costs import month_budget
from app.coach.engine import (
    CoachEvent,
    DoneEvent,
    Engine,
    ErrorEvent,
    PlanEvent,
    TextEvent,
    ToolEvent,
)
from app.coach.gemini import GeminiLLM
from app.coach.llm import LLM, AnthropicLLM
from app.coach.plans import plan_data
from app.coach.tools import ALL_TOOLS
from app.config import Settings, get_settings
from app.db.models import CoachConversation, CoachMemory, CoachPlan
from app.db.session import get_db, provide_session_factory
from app.db.types import utc_now
from app.repositories import coach as coach_repo
from app.services.weeks import current_week

router = APIRouter(prefix="/coach", tags=["coach"])

MAX_QUESTION_CHARS = 4000
MAX_MEMORY_CHARS = 300


class CoachName(StrEnum):
    TRAINING = "training"  # musculation et cardio
    LONGEVITY = "longevity"  # santé sur le long terme


def get_llm(settings: Settings = Depends(get_settings)) -> LLM | None:
    """The real model (Gemini or Claude, see Settings.provider), or None without a key.

    Tests replace this dependency.
    """
    if settings.provider is None:
        return None
    key = settings.api_key_for(settings.provider)
    return GeminiLLM(key) if settings.provider == "gemini" else AnthropicLLM(key)


# --- Status --------------------------------------------------------------------------


class BudgetOut(BaseModel):
    month: str
    spent_eur: float
    limit_eur: float
    warning: bool  # 80 % reached
    exhausted: bool


class StatusOut(BaseModel):
    configured: bool  # an API key is set in .env
    model: str
    budget: BudgetOut


@router.get("/status", response_model=StatusOut)
def read_status(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> StatusOut:
    budget = month_budget(db, utc_now(), settings)
    return StatusOut(
        configured=settings.provider is not None,
        model=settings.main_model,
        budget=BudgetOut(
            month=budget.month,
            spent_eur=round(budget.spent_eur, 4),
            limit_eur=budget.limit_eur,
            warning=budget.warning,
            exhausted=budget.exhausted,
        ),
    )


# --- Conversations ---------------------------------------------------------------------


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class PlanSessionOut(BaseModel):
    day: date
    kind: str  # run, ride, strength, class, walk, mobility, rest, other
    title: str
    duration_min: int
    intensity: str
    details: str
    why: str


class PlanOut(BaseModel):
    id: int
    coach: str
    week_start: date  # Monday
    summary: str
    sessions: list[PlanSessionOut]
    status: str  # proposed, accepted, rejected, replaced


class ShownMessage(BaseModel):
    """A message as the screen shows it: text, the tools the coach used, its plans."""

    role: str  # "user" or "assistant"
    text: str
    tools: list[str]  # French labels, e.g. "lit ton sommeil"
    plans: list[PlanOut] = []


class ConversationDetailOut(ConversationOut):
    messages: list[ShownMessage]


def _conversation_out(conversation: CoachConversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _shown(db: Session, conversation: CoachConversation) -> list[ShownMessage]:
    """Merge the model's messages into what a chat shows.

    Tool results (stored with role "user") are not shown; the tools called
    during an answer are attached to the coach's next text.
    """
    plans = coach_repo.plans_by_id(
        db, [i for m in conversation.messages if m.role == "user" for i in _plan_ids(m.content)]
    )
    shown: list[ShownMessage] = []
    pending_tools: list[str] = []
    pending_plans: list[PlanOut] = []
    for message in conversation.messages:
        text = "".join(b.get("text", "") for b in message.content if b.get("type") == "text")
        if message.role == "assistant":
            for block in message.content:
                if block.get("type") == "tool_use" and block["name"] in ALL_TOOLS:
                    pending_tools.append(ALL_TOOLS[block["name"]].label)
            if text:
                shown.append(
                    ShownMessage(
                        role="assistant", text=text, tools=pending_tools, plans=pending_plans
                    )
                )
                pending_tools, pending_plans = [], []
        else:
            pending_plans += [
                PlanOut.model_validate(plan_data(plans[i]))
                for i in _plan_ids(message.content)
                if i in plans
            ]
            if text:
                shown.append(ShownMessage(role="user", text=text, tools=[]))
    return shown


def _plan_ids(blocks: list[dict[str, Any]]) -> list[int]:
    """Ids of the plans proposed in these tool results (``{"plan_id": 3, ...}``)."""
    ids = []
    for block in blocks:
        if block.get("type") != "tool_result" or block.get("is_error"):
            continue
        try:
            plan_id = json.loads(block.get("content") or "{}").get("plan_id")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(plan_id, int):
            ids.append(plan_id)
    return ids


def _get(db: Session, conversation_id: int) -> CoachConversation:
    conversation = coach_repo.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("/{coach}/conversations", response_model=list[ConversationOut])
def list_conversations(coach: CoachName, db: Session = Depends(get_db)) -> list[ConversationOut]:
    return [_conversation_out(c) for c in coach_repo.list_conversations(db, coach)]


@router.post(
    "/{coach}/conversations",
    response_model=ConversationDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(coach: CoachName, db: Session = Depends(get_db)) -> ConversationDetailOut:
    conversation = coach_repo.create_conversation(db, coach)
    db.commit()
    return ConversationDetailOut(**_conversation_out(conversation).model_dump(), messages=[])


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def read_conversation(conversation_id: int, db: Session = Depends(get_db)) -> ConversationDetailOut:
    conversation = _get(db, conversation_id)
    return ConversationDetailOut(
        **_conversation_out(conversation).model_dump(), messages=_shown(db, conversation)
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)) -> None:
    coach_repo.delete_conversation(db, _get(db, conversation_id))
    db.commit()


# --- The answer (streamed) ---------------------------------------------------------------


class QuestionIn(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_CHARS)]


def _sse(event: CoachEvent) -> str:
    """One Server-Sent Event: ``event: <name>`` and a JSON ``data`` line."""
    data: dict[str, Any]
    if isinstance(event, TextEvent):
        name, data = "text", {"text": event.text}
    elif isinstance(event, ToolEvent):
        name, data = "tool", {"name": event.name, "label": event.label}
    elif isinstance(event, PlanEvent):
        name, data = "plan", event.plan
    elif isinstance(event, DoneEvent):
        name, data = "done", vars(event)
    else:
        name, data = "error", {"message": event.message}
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conversation_id}/messages")
def ask(
    conversation_id: int,
    payload: QuestionIn,
    factory: sessionmaker[Session] = Depends(provide_session_factory),
    settings: Settings = Depends(get_settings),
    llm: LLM | None = Depends(get_llm),
) -> StreamingResponse:
    with factory() as db:
        _get(db, conversation_id)  # 404 before the stream starts

    def events() -> Iterator[str]:
        # The stream outlives the request handler: it opens its own session.
        with factory() as db:
            if llm is None:
                message = "Le coach attend ta clé API : ajoute GEMINI_API_KEY dans .env."
                yield _sse(ErrorEvent(message))
                return
            conversation = _get(db, conversation_id)
            engine = Engine(db, settings, llm, utc_now())
            for event in engine.answer(conversation, payload.text.strip()):
                yield _sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # No caching or buffering by a proxy: each event must arrive at once.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Weekly plans ------------------------------------------------------------------------


class CurrentPlansOut(BaseModel):
    this_week: PlanOut | None  # the accepted plan of the current week
    next_week: PlanOut | None


class PlanDecision(BaseModel):
    accepted: bool


def _plan_out(plan: CoachPlan | None) -> PlanOut | None:
    return PlanOut.model_validate(plan_data(plan)) if plan else None


@router.get("/plans/current", response_model=CurrentPlansOut)
def read_current_plans(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> CurrentPlansOut:
    """The accepted plans of this week and the next one (Accueil page)."""
    monday = current_week(settings.app_timezone, utc_now()).monday
    return CurrentPlansOut(
        this_week=_plan_out(coach_repo.accepted_plan(db, monday)),
        next_week=_plan_out(coach_repo.accepted_plan(db, monday + timedelta(days=7))),
    )


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def decide_plan(plan_id: int, payload: PlanDecision, db: Session = Depends(get_db)) -> PlanOut:
    """Accept a proposed plan (it replaces the week's previous one) or reject it."""
    plan = coach_repo.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    coach_repo.decide_plan(db, plan, payload.accepted)
    db.commit()
    return PlanOut.model_validate(plan_data(plan))


# --- Memories ------------------------------------------------------------------------------


class MemoryOut(BaseModel):
    id: int
    text: str
    status: str  # "proposed" (by the coach) or "accepted"


class MemoryIn(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=MAX_MEMORY_CHARS)]


class MemoryUpdate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=MAX_MEMORY_CHARS)] | None = None
    accepted: bool | None = None


def _memory_out(memory: CoachMemory) -> MemoryOut:
    return MemoryOut(id=memory.id, text=memory.text, status=memory.status)


def _memory(db: Session, memory_id: int) -> CoachMemory:
    memory = coach_repo.get_memory(db, memory_id)
    if memory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    return memory


@router.get("/{coach}/memories", response_model=list[MemoryOut])
def list_memories(coach: CoachName, db: Session = Depends(get_db)) -> list[MemoryOut]:
    return [_memory_out(m) for m in coach_repo.list_memories(db, coach)]


@router.post("/{coach}/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def add_memory(coach: CoachName, payload: MemoryIn, db: Session = Depends(get_db)) -> MemoryOut:
    memory = coach_repo.add_memory(db, coach, payload.text.strip())
    db.commit()
    return _memory_out(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: int, payload: MemoryUpdate, db: Session = Depends(get_db)
) -> MemoryOut:
    """Accept a proposal, or correct the text."""
    memory = _memory(db, memory_id)
    if payload.text is not None:
        memory.text = payload.text.strip()
    if payload.accepted:
        memory.status = "accepted"
    db.commit()
    return _memory_out(memory)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: int, db: Session = Depends(get_db)) -> None:
    coach_repo.delete_memory(db, _memory(db, memory_id))
    db.commit()
