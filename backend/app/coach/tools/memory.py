"""The one tool that writes: the coach *proposes* something to remember.

A proposal is stored as "proposed" and does nothing until FRANKS accepts it on
the coach screen. That keeps him in control of what the coach knows, and a
message hidden in an activity name could never plant a durable instruction.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.coach.tools.base import Tool, ToolContext
from app.repositories import coach as coach_repo


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(
        min_length=3,
        max_length=300,
        description="One durable fact in French, e.g. « Douleur au genou gauche depuis "
        "septembre » or « Préfère courir le matin ».",
    )


def propose_memory(ctx: ToolContext, args: MemoryInput) -> dict[str, Any]:
    memory = coach_repo.propose_memory(ctx.db, ctx.coach, args.text.strip())
    return {
        "status": "proposed",
        "id": memory.id,
        "note": "FRANKS will accept or reject it on the coach screen; do not treat it as "
        "known until it appears in the memory block.",
    }


TOOLS = [
    Tool(
        "propose_memory",
        "Propose a durable fact to remember across conversations (goal, injury, constraint, "
        "preference) that FRANKS stated himself. Only when it will still matter in weeks; "
        "never for data the other tools can read.",
        "propose un souvenir",
        MemoryInput,
        propose_memory,
    ),
]
