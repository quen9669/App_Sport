"""What a coach tool is, and how one is run.

A tool is a typed, read-only Python function. The model sees its name, its
description and the JSON schema of its input (generated from a Pydantic
model); when it asks for the tool, the input is validated by Pydantic before
the function runs, so a malformed request becomes a clear error for the model
instead of a crash.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings

# Results longer than this are cut: a tool must answer with a summary, not a dump.
MAX_RESULT_CHARS = 20_000


@dataclass(frozen=True)
class ToolContext:
    db: Session
    settings: Settings
    coach: str
    now: datetime  # UTC, injected so tests can fix the date
    conversation_id: int | None = None  # where a proposed plan comes from

    @property
    def timezone(self) -> str:
        return self.settings.app_timezone

    @property
    def today(self) -> date:
        return self.now.astimezone(ZoneInfo(self.timezone)).date()


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Days(BaseModel):
    """The common "period" input: the last N days, today included."""

    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=28, ge=1, le=365, description="Number of days back from today.")


class Weeks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weeks: int = Field(default=8, ge=1, le=52, description="Number of ISO weeks, current included.")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str  # for the model (English, like the code)
    label: str  # for FRANKS, in French, shown while the tool runs: "lit ton sommeil"
    input_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], Any]

    def schema(self) -> dict[str, Any]:
        """Definition sent to the model."""
        schema = _inline_refs(self.input_model.model_json_schema())
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace ``{"$ref": "#/$defs/X"}`` by X itself.

    Pydantic puts nested models (a plan's sessions) in ``$defs``; a flat schema
    is understood the same way by every model provider.
    """
    definitions = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(definitions[node["$ref"].split("/")[-1]])
            return {key: resolve(value) for key, value in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    result: dict[str, Any] = resolve(schema)
    return result


def run_tool(tool: Tool, ctx: ToolContext, raw_input: Any) -> tuple[str, bool]:
    """Run one tool call: (JSON result for the model, whether it is an error)."""
    try:
        arguments = tool.input_model.model_validate(raw_input or {})
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        return json.dumps({"error": f"invalid input: {problems}"}), True
    result = tool.handler(ctx, arguments)
    text = json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '..."(truncated)"'
    return text, False


def rounded(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)
