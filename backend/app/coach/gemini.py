"""The coaches' model through Google's Gemini API (``generateContent``, REST).

Why REST with httpx rather than Google's SDK? httpx is already used for
Strava, the API is a single URL, and tests fake it with ``respx`` like every
other external API. Why ``generateContent`` and not the newer Interactions
API? It is stateless: the app sends the whole conversation each time and
nothing is kept on Google's side between calls (``store`` is not involved).

The engine speaks Anthropic's message format (see llm.py), so this class
translates in both directions:

- ``text`` blocks            <-> ``{"text": ...}`` parts
- ``tool_use`` blocks        <-> ``{"functionCall": {"name", "args", "id"}}`` parts
- ``tool_result`` blocks      -> ``{"functionResponse": {"name", "response", "id"}}`` parts

Gemini 3 also returns a ``thoughtSignature`` (an opaque token of its
reasoning) on some parts, and refuses the next call (error 400) if the
signature of a function call is not sent back. It is kept in the stored block
under ``thought_signature``; the Claude class removes that key.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx

from app.coach.llm import Final, LLMError, StreamEvent, TextDelta, ToolStart, Usage

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
# Gemini 3 thinks before answering, and thinking counts in the output limit:
# extra room so a long reflection does not cut the answer itself.
THINKING_ALLOWANCE = 4000
# A function call kept from a conversation started with Claude has no signature:
# Google documents this value to skip the check for such history.
NO_SIGNATURE = "skip_thought_signature_validator"
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# --- Request: Anthropic format -> Gemini format -----------------------------------


def system_instruction(system: list[dict[str, Any]]) -> dict[str, Any]:
    # ``cache_control`` is dropped: Gemini caches repeated prompt starts by itself.
    return {"parts": [{"text": block["text"]} for block in system]}


def function_declarations(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tool schemas; ``parametersJsonSchema`` accepts the full JSON Schema Pydantic writes."""
    declarations = [
        {
            "name": tool["name"],
            "description": tool["description"],
            "parametersJsonSchema": tool["input_schema"],
        }
        for tool in tools
    ]
    return [{"functionDeclarations": declarations}] if declarations else []


def _tool_names(messages: list[dict[str, Any]]) -> dict[str, str]:
    """Tool call id -> tool name: a Gemini function response must repeat the name."""
    return {
        block["id"]: block["name"]
        for message in messages
        for block in message["content"]
        if block.get("type") == "tool_use"
    }


def _part(block: dict[str, Any], names: dict[str, str], first_call: bool) -> dict[str, Any]:
    kind = block.get("type")
    if kind == "text":
        part: dict[str, Any] = {"text": block["text"]}
    elif kind == "tool_use":
        call = {"name": block["name"], "args": block.get("input") or {}, "id": block["id"]}
        part = {"functionCall": call}
        if first_call and "thought_signature" not in block:
            part["thoughtSignature"] = NO_SIGNATURE
    elif kind == "tool_result":
        data = _json(block.get("content"))
        response = {"error": data} if block.get("is_error") else {"output": data}
        name = names.get(block["tool_use_id"], "unknown")
        part = {
            "functionResponse": {"name": name, "response": response, "id": block["tool_use_id"]}
        }
    else:
        raise ValueError(f"Unknown block type: {kind}")
    if "thought_signature" in block:
        part["thoughtSignature"] = block["thought_signature"]
    return part


def _json(content: Any) -> Any:
    """Tool results are stored as JSON text; Gemini wants an object."""
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = _tool_names(messages)
    result = []
    for message in messages:
        parts = []
        first_call = True  # Gemini checks the signature of the first call of each step
        for block in message["content"]:
            parts.append(_part(block, names, first_call))
            if block.get("type") == "tool_use":
                first_call = False
        # Gemini's roles are "user" and "model"; tool results are sent as "user".
        result.append(
            {"role": "model" if message["role"] == "assistant" else "user", "parts": parts}
        )
    return result


# --- Response: Gemini parts -> Anthropic blocks ----------------------------------


class _Answer:
    """Collects the streamed parts into blocks, like Anthropic's final message."""

    def __init__(self) -> None:
        self.blocks: list[dict[str, Any]] = []
        self.finish_reason: str | None = None
        self.usage: dict[str, Any] = {}

    def add(self, part: dict[str, Any]) -> Iterator[StreamEvent]:
        if part.get("thought"):  # a thought summary (not requested): never shown
            return
        signature = part.get("thoughtSignature")
        if "functionCall" in part:
            call = part["functionCall"]
            block: dict[str, Any] = {
                "type": "tool_use",
                # Older models send no id: the engine needs one to match the result.
                "id": call.get("id") or f"call_{len(self.blocks)}",
                "name": call["name"],
                "input": call.get("args") or {},
            }
            if signature:
                block["thought_signature"] = signature
            self.blocks.append(block)
            yield ToolStart(call["name"])
        elif "text" in part:
            last = self.blocks[-1] if self.blocks else None
            if last and last["type"] == "text" and not signature:
                last["text"] += part["text"]  # the text arrives in pieces: one block
            else:
                block = {"type": "text", "text": part["text"]}
                if signature:
                    block["thought_signature"] = signature
                self.blocks.append(block)
            if part["text"]:
                yield TextDelta(part["text"])
        elif signature and self.blocks:
            # A signature alone, at the end of a text: kept on that text.
            self.blocks[-1].setdefault("thought_signature", signature)

    def final(self) -> Final:
        if any(block["type"] == "tool_use" for block in self.blocks):
            stop = "tool_use"
        elif self.finish_reason == "MAX_TOKENS":
            stop = "max_tokens"
        else:
            stop = "end_turn"
        # Gemini counts cached tokens inside promptTokenCount, Anthropic apart:
        # the engine uses Anthropic's meaning (input = not cached). Thinking is
        # billed as output.
        cached = self.usage.get("cachedContentTokenCount", 0)
        usage = Usage(
            input_tokens=self.usage.get("promptTokenCount", 0) - cached,
            output_tokens=self.usage.get("candidatesTokenCount", 0)
            + self.usage.get("thoughtsTokenCount", 0),
            cache_read_tokens=cached,
        )
        blocks = [b for b in self.blocks if b["type"] != "text" or b["text"]] or [
            {"type": "text", "text": ""}
        ]
        return Final(content=blocks, stop_reason=stop, usage=usage)


def _error(status: int, body: str) -> LLMError:
    if status in (401, 403) or "API_KEY_INVALID" in body:
        return LLMError("Clé API Gemini refusée : vérifie GEMINI_API_KEY dans .env.")
    if status == 429:
        return LLMError(
            "Quota de l'API Gemini atteint (l'offre gratuite est très limitée) : "
            "réessaie plus tard, ou active la facturation dans Google AI Studio."
        )
    return LLMError(f"L'API Gemini a répondu une erreur ({status}).")


class GeminiLLM:
    """The real model, through Gemini's REST API."""

    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
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
            "systemInstruction": system_instruction(system),
            "contents": contents(messages),
            "generationConfig": {
                "maxOutputTokens": max_tokens + THINKING_ALLOWANCE,
                # "low": enough to pick tools and reason on a few numbers, cheaper.
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        if tools:
            body["tools"] = function_declarations(tools)
        answer = _Answer()
        try:
            # The key goes in a header, never in the URL: URLs end up in logs.
            with self._client.stream(
                "POST",
                API_URL.format(model=model),
                params={"alt": "sse"},
                headers={"x-goog-api-key": self._api_key},
                json=body,
            ) as response:
                if response.status_code >= 400:
                    raise _error(response.status_code, response.read().decode(errors="replace"))
                for chunk in _sse_chunks(response.iter_lines()):
                    yield from _read_chunk(answer, chunk)
        except httpx.TransportError:
            raise LLMError("Impossible de joindre l'API Gemini (connexion internet ?).") from None
        yield answer.final()


def _sse_chunks(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """With ``alt=sse`` every chunk is one ``data: {...}`` line."""
    for line in lines:
        if line.startswith("data:"):
            yield json.loads(line[5:])


def _read_chunk(answer: _Answer, chunk: dict[str, Any]) -> Iterator[StreamEvent]:
    if "usageMetadata" in chunk:
        answer.usage = chunk["usageMetadata"]  # cumulative: the last one is the total
    candidates = chunk.get("candidates") or []
    if not candidates:
        if chunk.get("promptFeedback", {}).get("blockReason"):
            raise LLMError("Gemini a refusé de répondre à cette question (filtre de sécurité).")
        return
    candidate = candidates[0]
    for part in candidate.get("content", {}).get("parts", []):
        yield from answer.add(part)
    if candidate.get("finishReason"):
        answer.finish_reason = candidate["finishReason"]
