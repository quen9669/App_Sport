"""daily intensity minutes

Revision ID: 5974acb22aa2
Revises: 5bf6d8c96b49
Create Date: 2026-10-18 13:20:51.306704

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5974acb22aa2"
down_revision: str | Sequence[str] | None = "5bf6d8c96b49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("daily_health", schema=None) as batch_op:
        batch_op.add_column(sa.Column("intensity_moderate_min", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("intensity_vigorous_min", sa.Integer(), nullable=True))
    _fill_from_raw_payloads()


def _fill_from_raw_payloads() -> None:
    """Days already synced keep Garmin's full answer in raw_payload: read the
    intensity minutes from it, so the history shows up without re-syncing."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT source, external_id, payload FROM raw_payload WHERE kind = 'daily_health'")
    )
    for source, day, payload in rows.fetchall():
        stats = _stats(payload)
        moderate = _minutes(stats.get("moderateIntensityMinutes"))
        vigorous = _minutes(stats.get("vigorousIntensityMinutes"))
        if moderate is None and vigorous is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE daily_health SET intensity_moderate_min = :moderate, "
                "intensity_vigorous_min = :vigorous WHERE source = :source AND day = :day"
            ),
            {"moderate": moderate, "vigorous": vigorous, "source": source, "day": day},
        )


def _stats(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):  # raw SQL may return the JSON as text
        payload = json.loads(payload)
    stats = payload.get("stats") if isinstance(payload, dict) else None
    return stats if isinstance(stats, dict) else {}


def _minutes(value: Any) -> int | None:
    """Same bounds as app/integrations/health/validation.py (minutes in a day)."""
    if isinstance(value, int | float) and 0 <= value <= 1440:
        return int(value)
    return None


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("daily_health", schema=None) as batch_op:
        batch_op.drop_column("intensity_vigorous_min")
        batch_op.drop_column("intensity_moderate_min")
