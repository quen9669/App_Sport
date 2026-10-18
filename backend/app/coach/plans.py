"""How a weekly plan is shown: one dict for the stream, the API and the Accueil page."""

from typing import Any

from app.db.models import CoachPlan

PLAN_TOOL = "propose_weekly_plan"


def plan_data(plan: CoachPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "coach": plan.coach,
        "week_start": plan.week_start.isoformat(),
        "summary": plan.summary,
        "sessions": plan.days,
        "status": plan.status,
    }
