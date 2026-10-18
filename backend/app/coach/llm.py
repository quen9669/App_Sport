"""What the engine needs from a model, and the Claude (Anthropic) implementation.

The engine works with three small event types instead of an SDK's own
classes, so tests can replace the model with a scripted fake (``FakeLLM`` in
tests/fixtures/fake_llm.py) and never call a real API. Gemini lives in
``gemini.py`` and speaks the same language.

Conversations are stored in Anthropic's message format (lists of ``text``,
``tool_use`` and ``tool_result`` blocks); the Gemini class translates.
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


# Keys a provider adds to stored blocks for itself (Gemini's thought signatures).
# They are removed before a block is sent to Claude, which rejects unknown fields.
PROVIDER_KEYS = {"thought_signature"}


def _for_claude(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def clean(content: Any) -> Any:
        if isinstance(content, str):  # a plain text message
            return content
        return [{k: v for k, v in block.items() if k not in PROVIDER_KEYS} for block in content]

    return [{**message, "content": clean(message["content"])} for message in messages]


class AnthropicLLM:
    """The real model, through the official ``anthropic`` SDK."""

    def __init__(self, api_key: str, http_client: Any = None) -> None:
        # Imported here: the SDK is only loaded when a coach is really used.
        import anthropic

        self._anthropic = anthropic
        # ``http_client``: tests pass one with a fake transport, so no request
        # ever leaves the machine.
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=2, http_client=http_client)

    def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> Iterator[StreamEvent]:
        try:
            with self._client.messages.stream(
                model=model,
                system=system,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                messages=_for_claude(messages),  # type: ignore[arg-type]
                max_tokens=max_tokens,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_start"
                        and event.content_block.type == "tool_use"
                    ):
                        yield ToolStart(event.content_block.name)
                    elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield TextDelta(event.delta.text)
                message = stream.get_final_message()
        except self._anthropic.AuthenticationError:
            raise LLMError(
                "Clé API Anthropic refusée : vérifie ANTHROPIC_API_KEY dans .env."
            ) from None
        except self._anthropic.RateLimitError:
            raise LLMError(
                "Trop de demandes pour l'API Anthropic : réessaie dans une minute."
            ) from None
        except self._anthropic.APIConnectionError:
            raise LLMError(
                "Impossible de joindre l'API Anthropic (connexion internet ?)."
            ) from None
        except self._anthropic.APIStatusError as error:
            raise LLMError(f"L'API Anthropic a répondu une erreur ({error.status_code}).") from None
        usage = message.usage
        yield Final(
            # Plain dicts: stored as JSON and sent back as they are on the next call.
            content=[block.model_dump(exclude_none=True) for block in message.content],
            stop_reason=message.stop_reason,
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
            ),
        )
