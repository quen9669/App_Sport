"""The weekly plan: the coach proposes a structured week, FRANKS accepts it or not.

The model has to fill a strict schema (checked by Pydantic): a day, a type of
session, a duration, an intensity and a reason for each session. A run also
gets its steps (``RunWorkout``: warm-up, blocks, cool-down) with pace ZONES,
which the app turns into paces and FRANKS can send to his Garmin watch. A plan is
only stored as "proposed"; the coach screen shows it as a card with
"Accepter" / "Modifier", and an accepted plan appears on the Accueil page.
It never changes the goals.
"""

from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.coach.tools.base import Tool, ToolContext
from app.repositories import coach as coach_repo
from app.services.workouts import RunWorkout

# How far ahead a plan can start: this week or one of the next two.
MAX_WEEKS_AHEAD = 2

SessionKind = Literal["run", "ride", "strength", "class", "walk", "mobility", "rest", "other"]


class PlanSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date = Field(description="Date of the session (YYYY-MM-DD), inside the planned week.")
    kind: SessionKind = Field(
        description="run, ride, strength (gym), class (Body Pump, cross training), walk, "
        "mobility (stretching, yoga), rest, other."
    )
    title: str = Field(min_length=2, max_length=80, description="Short title in French.")
    duration_min: int = Field(ge=0, le=300, description="Planned duration; 0 for rest.")
    intensity: str = Field(
        default="",
        max_length=80,
        description="Pace or intensity in French, e.g. « 6:00-6:20 /km (endurance) » or « RPE 7 ».",
    )
    details: str = Field(
        default="", max_length=300, description="Content in French (intervals, exercises...)."
    )
    why: str = Field(min_length=3, max_length=200, description="Why this session, in French.")
    workout: RunWorkout | None = Field(
        default=None,
        description="Runs only, and required for them: the steps (warm-up, blocks of "
        "repeats with recovery, cool-down) with pace ZONES, not numbers.",
    )

    @model_validator(mode="after")
    def _workout_for_runs_only(self) -> "PlanSession":
        if self.workout is not None and self.kind != "run":
            raise ValueError("workout is only for kind 'run'")
        return self


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    week_start: date = Field(description="Monday of the planned ISO week (YYYY-MM-DD).")
    summary: str = Field(
        min_length=3, max_length=400, description="The week's idea in one or two French sentences."
    )
    sessions: list[PlanSession] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def _inside_the_week(self) -> "PlanInput":
        if self.week_start.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        sunday = self.week_start + timedelta(days=6)
        for session in self.sessions:
            if not self.week_start <= session.day <= sunday:
                raise ValueError(f"{session.day} is not in the week of {self.week_start}")
        return self


def propose_weekly_plan(ctx: ToolContext, args: PlanInput) -> dict[str, Any]:
    this_monday = ctx.today - timedelta(days=ctx.today.weekday())
    latest = this_monday + timedelta(weeks=MAX_WEEKS_AHEAD)
    if not this_monday <= args.week_start <= latest:
        return {
            "error": f"week_start must be between {this_monday} (this week) and {latest}",
        }
    sessions = sorted(args.sessions, key=lambda s: s.day)
    plan = coach_repo.propose_plan(
        ctx.db,
        ctx.coach,
        ctx.conversation_id,
        args.week_start,
        args.summary.strip(),
        [s.model_dump(mode="json") for s in sessions],
    )
    return {
        "status": "proposed",
        "plan_id": plan.id,
        "note": "The plan is shown to FRANKS as a card with Accept / Modify: do not repeat "
        "every session in your text, just explain the main idea.",
    }


TOOLS = [
    Tool(
        "propose_weekly_plan",
        "Propose a structured plan for one ISO week (this week or the next two), when FRANKS "
        "asks for a plan or a week's schedule. Base it on his goals, recent load, recovery and "
        "pace zones (read them first). He will accept or modify it on screen.",
        "prépare un plan de semaine",
        PlanInput,
        propose_weekly_plan,
    ),
]
