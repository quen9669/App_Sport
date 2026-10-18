"""The coaches' tools, and which coach gets which.

All tools read FRANKS's data through the app's services (the same numbers as
the screens), except ``propose_memory`` which only stores a proposal.
"""

from app.coach.tools import activities, health, memory, profile, race
from app.coach.tools.base import Tool, ToolContext, run_tool

ALL_TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        *profile.TOOLS,
        *activities.TOOLS,
        *health.TOOLS,
        *race.TOOLS,
        *memory.TOOLS,
    ]
}

# The longevity coach (phase 5b) will get its own list.
COACH_TOOLS: dict[str, list[str]] = {
    "training": list(ALL_TOOLS),
}


def tools_for(coach: str) -> list[Tool]:
    return [ALL_TOOLS[name] for name in COACH_TOOLS[coach]]


__all__ = ["ALL_TOOLS", "Tool", "ToolContext", "run_tool", "tools_for"]
