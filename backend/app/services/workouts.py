"""Structured running workouts: warm-up, blocks of intervals, cool-down.

A run session of the weekly plan can carry a ``RunWorkout``. The coach fills it
with *pace zones* (easy, threshold, interval...), never with numbers: the app
turns each zone into a pace range from the current form (Daniels' VDOT, the
same paces as the Course page). That range goes to the watch when FRANKS
sends the session to Garmin Connect (``services/garmin_push.py``).

Why no free list of steps? A fixed shape (warm-up, 1-6 blocks, cool-down) is
easy for the model to fill, easy to edit on screen, and covers what a runner
does: intervals (6 × 800 m with 2 min jog), tempo (1 block of 20 min), long
easy run (1 block of 50 min).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.race.daniels import PaceZone

# "none" = no pace target (free jog, or a recovery done by feel).
PaceKey = Literal["none", "easy", "marathon", "threshold", "interval", "repetition"]

# Daniels gives one pace for threshold, interval and repetition: the watch gets a
# range of this many seconds on each side, so it does not beep at every stride.
SINGLE_PACE_MARGIN_S = 5.0


class WorkoutStep(BaseModel):
    """One step: a duration OR a distance, and a pace zone."""

    model_config = ConfigDict(extra="forbid")
    duration_s: int | None = Field(
        default=None, ge=10, le=4 * 3600, description="Length in seconds (or give distance_m)."
    )
    distance_m: int | None = Field(
        default=None, ge=50, le=50_000, description="Length in metres (or give duration_s)."
    )
    pace: PaceKey = Field(
        default="none", description="Pace zone; the app computes the actual pace."
    )

    @model_validator(mode="after")
    def _one_length(self) -> "WorkoutStep":
        if (self.duration_s is None) == (self.distance_m is None):
            raise ValueError("give exactly one of duration_s or distance_m")
        return self


class WorkoutBlock(BaseModel):
    """``repeats`` × (work, then recovery). One repeat without recovery = a steady run."""

    model_config = ConfigDict(extra="forbid")
    repeats: int = Field(default=1, ge=1, le=30)
    work: WorkoutStep
    recovery: WorkoutStep | None = Field(
        default=None, description="Recovery after each repeat (e.g. 2 min jog, pace none)."
    )


class RunWorkout(BaseModel):
    """A complete run: optional warm-up, 1 to 6 blocks, optional cool-down."""

    model_config = ConfigDict(extra="forbid")
    warmup: WorkoutStep | None = None
    blocks: list[WorkoutBlock] = Field(min_length=1, max_length=6)
    cooldown: WorkoutStep | None = None


# --- Paces -----------------------------------------------------------------------------


def pace_targets(zones: list[PaceZone]) -> dict[str, tuple[float, float]]:
    """Each zone as a (slow, fast) range in seconds per km, as the watch gets it.

    Empty when the form is unknown: the steps then go without a pace target.
    """
    targets: dict[str, tuple[float, float]] = {}
    for zone in zones:
        slow, fast = zone.slow_s_per_km, zone.fast_s_per_km
        if slow == fast:
            slow, fast = slow + SINGLE_PACE_MARGIN_S, fast - SINGLE_PACE_MARGIN_S
        targets[zone.key] = (round(slow), round(fast))
    return targets


def estimated_duration_s(workout: RunWorkout, targets: dict[str, tuple[float, float]]) -> int:
    """A rough total time (Garmin shows it); distances use the zone's middle pace."""

    def step_s(step: WorkoutStep | None) -> float:
        if step is None:
            return 0.0
        if step.duration_s is not None:
            return float(step.duration_s)
        slow, fast = targets.get(step.pace, (360.0, 360.0))  # unknown: 6:00 /km
        return (step.distance_m or 0) / 1000 * (slow + fast) / 2

    total = step_s(workout.warmup) + step_s(workout.cooldown)
    for block in workout.blocks:
        total += block.repeats * (step_s(block.work) + step_s(block.recovery))
    return round(total)


# --- Garmin Connect format ---------------------------------------------------------------
# The JSON the Garmin Connect website sends when you build a workout by hand. Ids
# come from Garmin's /workout-service/workout/types (same values as the
# ``garminconnect`` library's StepType, ConditionType and TargetType).

RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
STEP_TYPES = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
}
TIME = {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}
DISTANCE = {
    "conditionTypeId": 3,
    "conditionTypeKey": "distance",
    "displayOrder": 3,
    "displayable": True,
}
ITERATIONS = {
    "conditionTypeId": 7,
    "conditionTypeKey": "iterations",
    "displayOrder": 7,
    "displayable": False,
}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
PACE_TARGET = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6}


class _Counter:
    """Garmin numbers every step (repeat groups included) 1, 2, 3... in order."""

    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def _step(
    kind: str,
    step: WorkoutStep,
    order: _Counter,
    targets: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "ExecutableStepDTO",
        "stepOrder": order.next(),
        "stepType": STEP_TYPES[kind],
        "endCondition": TIME if step.duration_s is not None else DISTANCE,
        "endConditionValue": float(step.duration_s or step.distance_m or 0),
        "targetType": NO_TARGET,
    }
    if step.pace in targets:
        slow, fast = targets[step.pace]
        # Garmin wants speeds in m/s: the slow pace is the LOW value.
        data |= {
            "targetType": PACE_TARGET,
            "targetValueOne": round(1000 / slow, 4),
            "targetValueTwo": round(1000 / fast, 4),
        }
    return data


def _block(
    block: WorkoutBlock, order: _Counter, targets: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    if block.repeats == 1:
        steps = [_step("interval", block.work, order, targets)]
        if block.recovery is not None:
            steps.append(_step("recovery", block.recovery, order, targets))
        return steps
    group: dict[str, Any] = {
        "type": "RepeatGroupDTO",
        "stepOrder": order.next(),
        "stepType": STEP_TYPES["repeat"],
        "numberOfIterations": block.repeats,
        "endCondition": ITERATIONS,
        "endConditionValue": float(block.repeats),
        "smartRepeat": False,
    }
    inner = [_step("interval", block.work, order, targets)]
    if block.recovery is not None:
        inner.append(_step("recovery", block.recovery, order, targets))
    group["workoutSteps"] = inner
    return [group]


def garmin_payload(
    name: str, workout: RunWorkout, targets: dict[str, tuple[float, float]], description: str = ""
) -> dict[str, Any]:
    """The workout as Garmin Connect stores it (``upload_workout``)."""
    order = _Counter()
    steps: list[dict[str, Any]] = []
    if workout.warmup is not None:
        steps.append(_step("warmup", workout.warmup, order, targets))
    for block in workout.blocks:
        steps += _block(block, order, targets)
    if workout.cooldown is not None:
        steps.append(_step("cooldown", workout.cooldown, order, targets))
    return {
        "workoutName": name[:80],
        "description": description[:500],
        "sportType": RUNNING,
        "estimatedDurationInSecs": estimated_duration_s(workout, targets),
        "workoutSegments": [{"segmentOrder": 1, "sportType": RUNNING, "workoutSteps": steps}],
    }
