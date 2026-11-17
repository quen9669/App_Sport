"""What the engine needs from a model.

The engine works with three small event types instead of an SDK's own
classes, so tests can replace the model with a scripted fake (``FakeLLM`` in
tests/fixtures/fake_llm.py) and never call a real API. The real model is
reached through OmniRoute only (``omniroute.py``, référentiel R-05).

Conversations are stored in Anthropic's message format (lists of ``text``,
``tool_use`` and ``tool_result`` blocks): it is what the database already holds,
so ``omniroute.py`` translates instead of migrating old conversations.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class TextDelta:
    """A piece of the answer, shown at once (streaming)."""

    text: str


@dataclass(frozen=True)
class ToolStart:
    """The model starts calling a tool (shown as "lit ton sommeil...")."""

    name: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class Final:
    """The complete message at the end of one model call."""

    content: list[dict[str, Any]]  # blocks: {"type": "text"...} / {"type": "tool_use"...}
    stop_reason: str | None  # "end_turn", "tool_use", "max_tokens"...
    usage: Usage = field(default_factory=Usage)


StreamEvent = TextDelta | ToolStart | Final


class LLM(Protocol):
    """What the engine needs from a model: stream one answer."""

    def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> Iterator[StreamEvent]: ...


class LLMError(Exception):
    """The model API failed (network, quota, invalid key). The message is safe to show."""
