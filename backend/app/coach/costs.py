"""What the coaches cost: token prices, the log of every call and the monthly budget.

Prices come from the settings (see app/config.py), so a price change or a new
model only needs a line in ``.env``. Costs are estimates: the provider's
invoice (Google or Anthropic) is the reference.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coach.llm import Usage
from app.config import Settings
from app.db.models import CoachCall

# Cached input costs 10 % of the input price to read (both providers) and 125 %
# to write (Anthropic only: Gemini's automatic cache has no write cost).
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25
# The coach shows a warning when the month's spending reaches this share of the budget.
WARNING_SHARE = 0.8


def cost_eur(usage: Usage, model: str, settings: Settings) -> float:
    """Estimated cost of one call in euros."""
    price_in, price_out = settings.prices(model)
    dollars = (
        usage.input_tokens * price_in
        + usage.cache_read_tokens * price_in * CACHE_READ_FACTOR
        + usage.cache_write_tokens * price_in * CACHE_WRITE_FACTOR
        + usage.output_tokens * price_out
    ) / 1_000_000
    return dollars * settings.usd_to_eur


def log_call(
    db: Session,
    *,
    coach: str,
    conversation_id: int | None,
    purpose: str,
    model: str,
    usage: Usage,
    latency_ms: int,
    tools: list[str],
    settings: Settings,
    error: str | None = None,
) -> CoachCall:
    call = CoachCall(
        coach=coach,
        conversation_id=conversation_id,
        purpose=purpose,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        cost_eur=cost_eur(usage, model, settings),
        latency_ms=latency_ms,
        tools=",".join(tools)[:255],
        error=error,
    )
    db.add(call)
    db.flush()
    return call


@dataclass(frozen=True)
class Budget:
    month: str  # "2026-10"
    spent_eur: float
    limit_eur: float

    @property
    def exhausted(self) -> bool:
        return self.spent_eur >= self.limit_eur

    @property
    def warning(self) -> bool:
        return self.spent_eur >= self.limit_eur * WARNING_SHARE


def month_budget(db: Session, now: datetime, settings: Settings) -> Budget:
    """Spending of the current calendar month (UTC), both coaches together."""
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = db.scalar(select(func.sum(CoachCall.cost_eur)).where(CoachCall.created_at >= start))
    return Budget(f"{now:%Y-%m}", float(spent or 0.0), settings.coach_monthly_budget_eur)
