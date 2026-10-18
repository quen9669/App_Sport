"""A scripted stand-in for the model: tests never call the real Anthropic API.

Each call to ``stream`` plays the next scripted turn and records what the
engine sent (model, system blocks, tools, messages), so tests can check both
sides: what the coach received and what it did with the answer.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.coach.llm import Final, LLMError, StreamEvent, TextDelta, ToolStart, Usage


def text_turn(text: str, usage: Usage | None = None) -> Final:
    return Final(
        content=[{"type": "text", "text": text}],
        stop_reason="end_turn",
        usage=usage or Usage(input_tokens=1000, output_tokens=200),
    )


def tool_turn(*calls: tuple[str, dict[str, Any]], text: str = "") -> Final:
    """The model asks for one or more tools (``("get_sleep", {"days": 7})``)."""
    content: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
    content += [
        {"type": "tool_use", "id": f"toolu_{i}_{name}", "name": name, "input": arguments}
        for i, (name, arguments) in enumerate(calls)
    ]
    return Final(content=content, stop_reason="tool_use", usage=Usage(500, 50, 2000, 0))


@dataclass
class FakeLLM:
    turns: list[Final | LLMError] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def stream(self, **request: Any) -> Iterator[StreamEvent]:
        # A copy: the engine keeps appending to the same message list afterwards.
        self.calls.append({**request, "messages": [dict(m) for m in request["messages"]]})
        if not self.turns:
            raise AssertionError("FakeLLM: no scripted turn left")
        turn = self.turns.pop(0)
        if isinstance(turn, LLMError):
            raise turn
        for block in turn.content:
            if block["type"] == "text":
                # Two pieces, like real streaming.
                middle = len(block["text"]) // 2
                yield TextDelta(block["text"][:middle])
                yield TextDelta(block["text"][middle:])
            elif block["type"] == "tool_use":
                yield ToolStart(block["name"])
        yield turn

    def tool_results(self, call_index: int) -> list[dict[str, Any]]:
        """The tool_result blocks the engine sent in a given call."""
        last = self.calls[call_index]["messages"][-1]
        return [b for b in last["content"] if b.get("type") == "tool_result"]
