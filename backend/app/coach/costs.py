"""What the coaches cost: token prices and the log of every call.

Prices come from the settings (see app/config.py), so a price change or a new
model only needs a line in ``.env``. Costs are estimates: the provider's
quota and dashboard in OmniRoute are the reference.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coach.llm import Usage
from app.config import Settings
from app.db.models import CoachCall

# Cached input costs 10 % of the input price to read and 125 % to write.
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25


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


def month_spent(db: Session, now: datetime) -> tuple[str, float]:
    """("2026-11", estimated euros) of the current calendar month (UTC), both coaches.

    Shown for information only: the budget is enforced by OmniRoute, never by the
    app (référentiel R-07, écart SPT-02).
    """
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = db.scalar(select(func.sum(CoachCall.cost_eur)).where(CoachCall.created_at >= start))
    return f"{now:%Y-%m}", float(spent or 0.0)
