"""Tests for the Gemini model class and the choice of provider.

The Gemini API is faked with ``respx`` (it intercepts httpx): no request ever
leaves the machine.
"""

import json
from typing import Any

import httpx
import pytest
import respx

from app.api.coach import get_llm
from app.coach.costs import cost_eur
from app.coach.gemini import NO_SIGNATURE, GeminiLLM, contents
from app.coach.llm import AnthropicLLM, Final, LLMError, TextDelta, ToolStart, Usage, _for_claude
from app.config import Settings

URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-x:streamGenerateContent"


def sse(*chunks: dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(chunk)}\r\n\r\n" for chunk in chunks)
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


def parts(*items: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
    candidate: dict[str, Any] = {"content": {"role": "model", "parts": list(items)}}
    if finish:
        candidate["finishReason"] = finish
    return {"candidates": [candidate]}


def ask(**kwargs: Any) -> list[Any]:
    arguments: dict[str, Any] = {
        "model": "gemini-x",
        "system": [
            {"type": "text", "text": "Tu es coach.", "cache_control": {"type": "ephemeral"}}
        ],
        "tools": [],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Salut"}]}],
        "max_tokens": 100,
    }
    return list(GeminiLLM("gm-key").stream(**(arguments | kwargs)))


@respx.mock
def test_streams_text_and_a_tool_call() -> None:
    route = respx.post(URL).mock(
        return_value=sse(
            parts({"text": "Je regarde "}),
            parts({"text": "ton sommeil."}),
            parts(
                {
                    "functionCall": {"name": "get_sleep", "args": {"days": 7}, "id": "c1"},
                    "thoughtSignature": "sig-A",
                },
                finish="STOP",
            )
            | {
                "usageMetadata": {
                    "promptTokenCount": 1000,
                    "cachedContentTokenCount": 800,
                    "candidatesTokenCount": 20,
                    "thoughtsTokenCount": 30,
                }
            },
        )
    )
    tool = {"name": "get_sleep", "description": "Sommeil", "input_schema": {"type": "object"}}
    events = ask(tools=[tool])

    assert events[:3] == [
        TextDelta("Je regarde "),
        TextDelta("ton sommeil."),
        ToolStart("get_sleep"),
    ]
    final = events[-1]
    assert isinstance(final, Final) and final.stop_reason == "tool_use"
    assert final.content == [
        {"type": "text", "text": "Je regarde ton sommeil."},
        {
            "type": "tool_use",
            "id": "c1",
            "name": "get_sleep",
            "input": {"days": 7},
            "thought_signature": "sig-A",
        },
    ]
    # Cached tokens are counted apart, thinking is output.
    assert final.usage == Usage(input_tokens=200, output_tokens=50, cache_read_tokens=800)

    request = route.calls.last.request
    assert request.headers["x-goog-api-key"] == "gm-key"
    assert "gm-key" not in str(request.url)  # never in the URL (logs)
    assert request.url.params["alt"] == "sse"
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "Tu es coach."}]}
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert declaration["parametersJsonSchema"] == {"type": "object"}


def test_history_is_translated_with_signatures_and_tool_names() -> None:
    history: list[dict[str, Any]] = [
        {"role": "user", "content": [{"type": "text", "text": "Mon sommeil ?"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "c1",
                    "name": "get_sleep",
                    "input": {},
                    "thought_signature": "s",
                },
                {"type": "tool_use", "id": "c2", "name": "get_profile", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "c1", "content": '{"nights": 7}'},
                {
                    "type": "tool_result",
                    "tool_use_id": "c2",
                    "content": '{"error": "x"}',
                    "is_error": True,
                },
            ],
        },
    ]
    model, results = contents(history)[1:]
    assert model["role"] == "model"
    assert model["parts"][0]["thoughtSignature"] == "s"
    assert "thoughtSignature" not in model["parts"][1]  # only the first call of a step
    assert results["role"] == "user"
    assert results["parts"][0]["functionResponse"] == {
        "name": "get_sleep",
        "response": {"output": {"nights": 7}},
        "id": "c1",
    }
    assert results["parts"][1]["functionResponse"]["response"] == {"error": {"error": "x"}}


def test_calls_from_a_claude_conversation_get_the_documented_placeholder() -> None:
    history: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t", "name": "a", "input": {}}],
        }
    ]
    assert contents(history)[0]["parts"][0]["thoughtSignature"] == NO_SIGNATURE


def test_claude_never_receives_gemini_keys() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "assistant", "content": [{"type": "text", "text": "x", "thought_signature": "s"}]},
        {"role": "user", "content": "plain text"},
    ]
    assert _for_claude(messages) == [
        {"role": "assistant", "content": [{"type": "text", "text": "x"}]},
        {"role": "user", "content": "plain text"},
    ]


@respx.mock
@pytest.mark.parametrize(
    ("status", "message"),
    [(400, "Clé API Gemini refusée"), (429, "Quota de l'API Gemini"), (500, r"erreur \(500\)")],
)
def test_errors_become_french_messages(status: int, message: str) -> None:
    body = (
        {
            "error": {
                "status": "INVALID_ARGUMENT",
                "message": "API key not valid",
                "details": [{"reason": "API_KEY_INVALID"}],
            }
        }
        if status == 400
        else {"error": {}}
    )
    respx.post(URL).mock(return_value=httpx.Response(status, json=body))
    with pytest.raises(LLMError, match=message):
        ask()


@respx.mock
def test_network_error() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectError("no network"))
    with pytest.raises(LLMError, match="Impossible de joindre l'API Gemini"):
        ask()


@respx.mock
def test_max_tokens_and_blocked_prompt() -> None:
    respx.post(URL).mock(return_value=sse(parts({"text": "Début"}, finish="MAX_TOKENS")))
    final = ask()[-1]
    assert final.stop_reason == "max_tokens"

    respx.post(URL).mock(return_value=sse({"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(LLMError, match="filtre de sécurité"):
        ask()


# --- Choosing the provider ---------------------------------------------------------


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)


def test_gemini_key_wins_unless_a_provider_is_forced() -> None:
    assert settings().provider is None
    assert settings(anthropic_api_key="a").provider == "anthropic"
    both = settings(anthropic_api_key="a", gemini_api_key="g")
    assert both.provider == "gemini"
    assert both.main_model == "gemini-3.8-flash"
    assert both.light_model == "gemini-3.5-flash-lite"
    forced = settings(anthropic_api_key="a", gemini_api_key="g", coach_provider="anthropic")
    assert (forced.provider, forced.main_model) == ("anthropic", "claude-sonnet-5-5")
    # A forced provider without its key: the coach is off, not silently switched.
    assert settings(gemini_api_key="g", coach_provider="anthropic").provider is None
    assert settings(coach_provider="", coach_price_input_usd="").coach_provider is None


def test_prices_follow_the_provider_and_can_be_overridden() -> None:
    gemini = settings(gemini_api_key="g", usd_to_eur=1)
    million = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost_eur(million, "gemini-3.8-flash", gemini) == pytest.approx(9.0)
    assert cost_eur(million, "gemini-3.5-flash-lite", gemini) == pytest.approx(2.8)
    cheaper = settings(gemini_api_key="g", usd_to_eur=1, coach_price_input_usd=0.75)
    assert cheaper.prices("gemini-3.8-flash") == (0.75, 7.5)


def test_the_route_builds_the_right_model() -> None:
    assert get_llm(settings()) is None
    assert isinstance(get_llm(settings(gemini_api_key="g")), GeminiLLM)
    assert isinstance(get_llm(settings(anthropic_api_key="a")), AnthropicLLM)
