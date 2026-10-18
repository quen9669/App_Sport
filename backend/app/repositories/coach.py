"""Database access for the coaches: conversations, messages, memories, call log."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CoachCall, CoachConversation, CoachMemory, CoachMessage

# --- Conversations ---------------------------------------------------------------


def list_conversations(db: Session, coach: str, limit: int = 50) -> list[CoachConversation]:
    """Most recent first."""
    query = (
        select(CoachConversation)
        .where(CoachConversation.coach == coach)
        .order_by(CoachConversation.updated_at.desc(), CoachConversation.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def create_conversation(db: Session, coach: str) -> CoachConversation:
    conversation = CoachConversation(coach=coach)
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation(db: Session, conversation_id: int) -> CoachConversation | None:
    return db.get(CoachConversation, conversation_id)


def delete_conversation(db: Session, conversation: CoachConversation) -> None:
    db.delete(conversation)
    db.flush()


def add_message(
    db: Session, conversation: CoachConversation, role: str, content: list[dict[str, Any]]
) -> CoachMessage:
    message = CoachMessage(
        conversation_id=conversation.id,
        position=len(conversation.messages),
        role=role,
        content=content,
    )
    conversation.messages.append(message)
    db.flush()
    return message


def previous_summaries(
    db: Session, coach: str, before_id: int, limit: int = 3
) -> list[CoachConversation]:
    """The latest earlier conversations that have a summary (oldest first)."""
    query = (
        select(CoachConversation)
        .where(
            CoachConversation.coach == coach,
            CoachConversation.id < before_id,
            CoachConversation.summary.is_not(None),
        )
        .order_by(CoachConversation.id.desc())
        .limit(limit)
    )
    return list(reversed(list(db.scalars(query))))


# --- Memories ------------------------------------------------------------------------


def list_memories(db: Session, coach: str) -> list[CoachMemory]:
    query = select(CoachMemory).where(CoachMemory.coach == coach).order_by(CoachMemory.id)
    return list(db.scalars(query))


def accepted_memories(db: Session, coach: str) -> list[CoachMemory]:
    return [m for m in list_memories(db, coach) if m.status == "accepted"]


def propose_memory(db: Session, coach: str, text: str) -> CoachMemory:
    memory = CoachMemory(coach=coach, text=text, status="proposed")
    db.add(memory)
    db.flush()
    return memory


def add_memory(db: Session, coach: str, text: str) -> CoachMemory:
    """A memory typed by FRANKS himself: accepted at once."""
    memory = CoachMemory(coach=coach, text=text, status="accepted")
    db.add(memory)
    db.flush()
    return memory


def get_memory(db: Session, memory_id: int) -> CoachMemory | None:
    return db.get(CoachMemory, memory_id)


def delete_memory(db: Session, memory: CoachMemory) -> None:
    db.delete(memory)
    db.flush()


# --- Call log --------------------------------------------------------------------------


def recent_calls(db: Session, limit: int = 20) -> list[CoachCall]:
    query = select(CoachCall).order_by(CoachCall.id.desc()).limit(limit)
    return list(db.scalars(query))
