"""The coaches' tools, and which coach gets which.

All tools read FRANKS's data through the app's services (the same numbers as
the screens), except ``propose_memory`` and ``propose_weekly_plan`` which only
store a proposal that FRANKS accepts or not.
"""

from app.coach.tools import activities, health, longevity, memory, plan, profile, race
from app.coach.tools.base import Tool, ToolContext, run_tool

ALL_TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        *profile.TOOLS,
        *activities.TOOLS,
        *health.TOOLS,
        *race.TOOLS,
        *longevity.TOOLS,
        *memory.TOOLS,
        *plan.TOOLS,
    ]
}

# The training coach plans the week; the longevity coach looks at the long term
# (no race paces, no weekly plan, but the smoke-free days).
_TRAINING_ONLY = {"get_race_predictions", "get_pace_zones", "propose_weekly_plan"}
_LONGEVITY_ONLY = {"get_smoke_free"}
COACH_TOOLS: dict[str, list[str]] = {
    "training": [name for name in ALL_TOOLS if name not in _LONGEVITY_ONLY],
    "longevity": [name for name in ALL_TOOLS if name not in _TRAINING_ONLY],
}


def tools_for(coach: str) -> list[Tool]:
    return [ALL_TOOLS[name] for name in COACH_TOOLS[coach]]


__all__ = ["ALL_TOOLS", "Tool", "ToolContext", "run_tool", "tools_for"]
