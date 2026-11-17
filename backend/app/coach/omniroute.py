"""The coaches' model, reached only through OmniRoute (référentiel R-05, écart SPT-01).

OmniRoute is the shared AI gateway of FRANKS's server (``http://omniroute:20128/v1``
on the Docker network ``llm-net``). It speaks the OpenAI "chat completions"
API, holds the real provider keys, and enforces the app's quota: the app only
knows its own OmniRoute key (``OMNIROUTE_API_KEY``, from the OpenBao vault).

Why plain httpx and not the ``openai`` SDK? httpx is already used for Strava,
it is one URL, and tests fake it with ``respx`` like every other external API.

The engine speaks Anthropic's message format (see llm.py), so this class
translates in both directions:

- ``text`` blocks        <-> ``content`` of a message
- ``tool_use`` blocks    <-> ``tool_calls`` of an assistant message
- ``tool_result`` blocks  -> one ``{"role": "tool"}`` message each
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx

from app.coach.llm import Final, LLMError, StreamEvent, TextDelta, ToolStart, Usage

TIMEOUT = httpx.Timeout(120.0, connect=10.0)
# Shown when OmniRoute refuses the key or the quota (SPT-02): the coach is
# "◆ Dégradé", the rest of the app keeps working.
DEGRADED = "◆ Coach dégradé : "


# --- Request: Anthropic format -> OpenAI format ------------------------------------


def system_text(system: list[dict[str, Any]]) -> str:
    # ``cache_control`` is Anthropic's: OmniRoute and the providers cache
    # repeated prompt starts by themselves.
    return "\n\n".join(block["text"] for block in system)


def functions(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]


def _text(blocks: list[dict[str, Any]]) -> str:
    return "".join(block["text"] for block in blocks if block.get("type") == "text")


def _assistant(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": _text(blocks) or None}
    calls = [
        {
            "id": block["id"],
            "type": "function",
            "function": {"name": block["name"], "arguments": json.dumps(block.get("input") or {})},
        }
        for block in blocks
        if block.get("type") == "tool_use"
    ]
    if calls:
        message["tool_calls"] = calls
    return message


def _user(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A user turn: tool results first (one message each), then any text."""
    result: list[dict[str, Any]] = [
        {"role": "tool", "tool_call_id": block["tool_use_id"], "content": block.get("content", "")}
        for block in blocks
        if block.get("type") == "tool_result"
    ]
    text = _text(blocks)
    if text:
        result.append({"role": "user", "content": text})
    return result


def chat_messages(system: list[dict[str, Any]], messages: list[dict[str, Any]]) -> list[Any]:
    result: list[Any] = [{"role": "system", "content": system_text(system)}]
    for message in messages:
        content = message["content"]
        # Old blocks may carry keys of a former provider (Gemini's thought
        # signatures): only the fields read below are sent, so they are ignored.
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        if message["role"] == "assistant":
            result.append(_assistant(blocks))
        else:
            result.extend(_user(blocks))
    return result


# --- Response: streamed OpenAI chunks -> Anthropic blocks ---------------------------


class _Answer:
    """Collects the streamed pieces into blocks, like Anthropic's final message."""

    def __init__(self) -> None:
        self.text = ""
        self.calls: dict[int, dict[str, str]] = {}  # index -> id, name, arguments
        self.finish_reason: str | None = None
        self.usage: dict[str, Any] = {}

    def add(self, delta: dict[str, Any]) -> Iterator[StreamEvent]:
        if delta.get("content"):
            self.text += delta["content"]
            yield TextDelta(delta["content"])
        for piece in delta.get("tool_calls") or []:
            call = self.calls.setdefault(piece.get("index", 0), {"id": "", "name": "", "args": ""})
            function = piece.get("function") or {}
            if piece.get("id"):
                call["id"] = piece["id"]
            if function.get("name"):
                call["name"] += function["name"]
                yield ToolStart(call["name"])
            call["args"] += function.get("arguments") or ""

    def final(self) -> Final:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": self.text}] if self.text else []
        for index, call in sorted(self.calls.items()):
            blocks.append(
                {
                    "type": "tool_use",
                    # The engine needs an id to match the result.
                    "id": call["id"] or f"call_{index}",
                    "name": call["name"],
                    "input": _arguments(call["args"]),
                }
            )
        if self.calls:
            stop = "tool_use"
        elif self.finish_reason == "length":
            stop = "max_tokens"
        else:
            stop = "end_turn"
        # OpenAI counts cached tokens inside prompt_tokens, Anthropic apart: the
        # engine uses Anthropic's meaning (input = not cached).
        cached = (self.usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        usage = Usage(
            input_tokens=(self.usage.get("prompt_tokens") or 0) - cached,
            output_tokens=self.usage.get("completion_tokens") or 0,
            cache_read_tokens=cached,
        )
        return Final(
            content=blocks or [{"type": "text", "text": ""}], stop_reason=stop, usage=usage
        )


def _arguments(text: str) -> dict[str, Any]:
    """Arguments arrive as JSON text; a broken one becomes {} and the tool says what is missing."""
    try:
        value = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _error(status: int) -> LLMError:
    if status in (401, 403):
        return LLMError(DEGRADED + "OmniRoute refuse la clé de l'app (clé bloquée ou invalide).")
    if status in (402, 429):
        return LLMError(DEGRADED + "quota OmniRoute atteint, réessaie plus tard.")
    return LLMError(f"OmniRoute a répondu une erreur ({status}).")


class OmniRouteLLM:
    """The real model, through OmniRoute's OpenAI-compatible API."""

    def __init__(
        self, base_url: str, api_key: str, http_client: httpx.Client | None = None
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=TIMEOUT)

    def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> Iterator[StreamEvent]:
        body: dict[str, Any] = {
            "model": model,
            "messages": chat_messages(system, messages),
            "max_tokens": max_tokens,
            "stream": True,
            # Token counts come in a last chunk: needed to log each call's cost.
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = functions(tools)
        answer = _Answer()
        try:
            with self._client.stream(
                "POST",
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            ) as response:
                if response.status_code >= 400:
                    raise _error(response.status_code)
                for chunk in _sse_chunks(response.iter_lines()):
                    yield from _read_chunk(answer, chunk)
        except httpx.TransportError:
            raise LLMError(DEGRADED + "OmniRoute est injoignable.") from None
        yield answer.final()


def _sse_chunks(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Every chunk is one ``data: {...}`` line; ``data: [DONE]`` ends the stream."""
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        yield json.loads(data)


def _read_chunk(answer: _Answer, chunk: dict[str, Any]) -> Iterator[StreamEvent]:
    if chunk.get("usage"):
        answer.usage = chunk["usage"]
    for choice in chunk.get("choices") or []:
        yield from answer.add(choice.get("delta") or {})
        if choice.get("finish_reason"):
            answer.finish_reason = choice["finish_reason"]
