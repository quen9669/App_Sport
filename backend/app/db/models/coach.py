"""AI coaches: conversations, messages, durable memory and the log of model calls.

Everything stays in the local database. Only what the coach asks for through
its tools is sent to the model, at the moment it needs it.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class CoachConversation(Base):
    __tablename__ = "coach_conversation"

    id: Mapped[int] = mapped_column(primary_key=True)
    coach: Mapped[str] = mapped_column(String(16), index=True)  # "training", "longevity"
    title: Mapped[str] = mapped_column(String(120), default="")  # first question, shortened
    # Summary of the messages that are no longer sent to the model (see
    # app/coach/history.py), and of the whole conversation for the next ones.
    summary: Mapped[str | None] = mapped_column(Text)
    # Messages before this position are covered by ``summary``.
    summarized_until: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    messages: Mapped[list["CoachMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CoachMessage.position",
    )


class CoachMessage(Base):
    """One message in the model's format: role + content blocks (text, tool calls, results)."""

    __tablename__ = "coach_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("coach_conversation.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)  # 0, 1, 2... in the conversation
    role: Mapped[str] = mapped_column(String(16))  # "user" or "assistant"
    content: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    conversation: Mapped[CoachConversation] = relationship(back_populates="messages")


class CoachMemory(Base):
    """Something durable the coach should remember (goal, injury, preference).

    The coach can only *propose* a memory; FRANKS accepts, edits or deletes it.
    Only accepted memories are given to the coach.
    """

    __tablename__ = "coach_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    coach: Mapped[str] = mapped_column(String(16), index=True)
    text: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed / accepted
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class CoachCall(Base):
    """One call to the model API: tokens, estimated cost, latency, tools used.

    Never the prompt itself nor any secret: just the numbers to follow costs.
    """

    __tablename__ = "coach_call"

    id: Mapped[int] = mapped_column(primary_key=True)
    coach: Mapped[str] = mapped_column(String(16), index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("coach_conversation.id", ondelete="SET NULL")
    )
    purpose: Mapped[str] = mapped_column(String(16), default="answer")  # "answer", "summary"
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tools: Mapped[str] = mapped_column(String(255), default="")  # comma-separated names
    error: Mapped[str | None] = mapped_column(String(255))  # type of error, never a message body
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
