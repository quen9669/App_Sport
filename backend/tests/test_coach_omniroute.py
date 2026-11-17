"""The OmniRoute model class (SPT-01), against a simulated HTTP API (respx).

OmniRoute speaks OpenAI's "chat completions" format; the engine stores
Anthropic-style blocks. These tests check the translation both ways, the
streaming, the token counts and the French "◆ Dégradé" errors (SPT-02).
"""

import json
from typing import Any

import httpx
import pytest
import respx

from app.api.coach import get_llm
from app.coach.llm import Final, LLMError, TextDelta, ToolStart
from app.coach.omniroute import OmniRouteLLM, chat_messages, functions
from app.config import Settings

BASE = "http://omniroute.test/v1"
URL = f"{BASE}/chat/completions"


def stream_body(*chunks: dict[str, Any]) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def ask(llm: OmniRouteLLM, **kwargs: Any) -> list[Any]:
    args: dict[str, Any] = {
        "model": "claude-sonnet-5-5",
        "system": [{"type": "text", "text": "Tu es un coach.", "cache_control": {}}],
        "tools": [],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Salut"}]}],
        "max_tokens": 100,
    }
    return list(llm.stream(**{**args, **kwargs}))


def test_history_is_translated_to_openai_messages() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": [{"type": "text", "text": "Mon sommeil ?"}]},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Je regarde."},
                # An old Gemini block: its extra key is never sent.
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "get_sleep",
                    "input": {"days": 7},
                    "thought_signature": "x",
                },
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"h": 7}'}],
        },
        {"role": "user", "content": "texte simple"},
    ]
    result = chat_messages([{"type": "text", "text": "A"}, {"type": "text", "text": "B"}], messages)
    assert result == [
        {"role": "system", "content": "A\n\nB"},
        {"role": "user", "content": "Mon sommeil ?"},
        {
            "role": "assistant",
            "content": "Je regarde.",
            "tool_calls": [
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "get_sleep", "arguments": '{"days": 7}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": '{"h": 7}'},
        {"role": "user", "content": "texte simple"},
    ]


def test_tools_become_functions() -> None:
    tool = {"name": "get_sleep", "description": "d", "input_schema": {"type": "object"}}
    assert functions([{**tool, "cache_control": {}}]) == [
        {
            "type": "function",
            "function": {"name": "get_sleep", "description": "d", "parameters": {"type": "object"}},
        }
    ]


@respx.mock
def test_streams_text_and_tool_calls_with_usage() -> None:
    body = stream_body(
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "Je "}}]},
        {"choices": [{"index": 0, "delta": {"content": "regarde"}}]},
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_a",
                                "type": "function",
                                "function": {"name": "get_sleep", "arguments": '{"da'},
                            }
                        ]
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ys": 7}'}}]},
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 30,
                "prompt_tokens_details": {"cached_tokens": 900},
            },
        },
    )
    route = respx.post(URL).mock(return_value=httpx.Response(200, text=body))
    tool = {"name": "get_sleep", "description": "d", "input_schema": {"type": "object"}}
    events = ask(OmniRouteLLM(BASE + "/", "key-app-sport"), tools=[tool])

    assert events[:3] == [TextDelta("Je "), TextDelta("regarde"), ToolStart("get_sleep")]
    final = events[-1]
    assert isinstance(final, Final) and final.stop_reason == "tool_use"
    assert final.content == [
        {"type": "text", "text": "Je regarde"},
        {"type": "tool_use", "id": "call_a", "name": "get_sleep", "input": {"days": 7}},
    ]
    usage = final.usage
    assert (usage.input_tokens, usage.cache_read_tokens, usage.output_tokens) == (100, 900, 30)

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer key-app-sport"
    sent = json.loads(request.content)
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    assert sent["tools"][0]["function"]["name"] == "get_sleep"


@respx.mock
def test_plain_answer_and_cut_answer() -> None:
    body = stream_body({"choices": [{"delta": {"content": "Bravo"}, "finish_reason": "length"}]})
    respx.post(URL).mock(return_value=httpx.Response(200, text=body))
    final = ask(OmniRouteLLM(BASE, "k"))[-1]
    assert final.content == [{"type": "text", "text": "Bravo"}]
    assert final.stop_reason == "max_tokens"


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "refuse la clé"), (403, "refuse la clé"), (429, "quota"), (402, "quota")],
)
@respx.mock
def test_refusals_put_the_coach_in_degraded_mode(status: int, message: str) -> None:
    respx.post(URL).mock(return_value=httpx.Response(status, json={"error": "no"}))
    with pytest.raises(LLMError, match=f"◆ Coach dégradé.*{message}"):
        ask(OmniRouteLLM(BASE, "k"))


@respx.mock
def test_unreachable_omniroute_is_degraded_too() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(LLMError, match="◆ Coach dégradé : OmniRoute est injoignable"):
        ask(OmniRouteLLM(BASE, "k"))


def test_the_coach_needs_only_the_omniroute_key() -> None:
    assert get_llm(Settings(omniroute_api_key="")) is None
    assert isinstance(get_llm(Settings(omniroute_api_key="k")), OmniRouteLLM)
    settings = Settings(omniroute_api_key="k")
    assert (settings.main_model, settings.light_model) == ("claude-sonnet-5-5", "claude-haiku-5-5")
    assert settings.prices("claude-haiku-5-5") == (1.0, 5.0)
