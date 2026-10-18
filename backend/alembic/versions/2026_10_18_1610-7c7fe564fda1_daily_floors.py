"""daily floors

Revision ID: 7c7fe564fda1
Revises: 4ae8dc6985f1
Create Date: 2026-10-18 16:10:02.846543

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c7fe564fda1"
down_revision: str | Sequence[str] | None = "4ae8dc6985f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("daily_health", schema=None) as batch_op:
        batch_op.add_column(sa.Column("floors_ascended", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("floors_descended", sa.Integer(), nullable=True))
    _fill_from_raw_payloads()


def _fill_from_raw_payloads() -> None:
    """Days already synced keep Garmin's full answer in raw_payload: read the
    floors from it, so the history shows up without re-syncing."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT source, external_id, payload FROM raw_payload WHERE kind = 'daily_health'")
    )
    for source, day, payload in rows.fetchall():
        stats = _stats(payload)
        up = _floors(stats.get("floorsAscended"))
        down = _floors(stats.get("floorsDescended"))
        if up is None and down is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE daily_health SET floors_ascended = :up, floors_descended = :down "
                "WHERE source = :source AND day = :day"
            ),
            {"up": up, "down": down, "source": source, "day": day},
        )


def _stats(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):  # raw SQL may return the JSON as text
        payload = json.loads(payload)
    stats = payload.get("stats") if isinstance(payload, dict) else None
    return stats if isinstance(stats, dict) else {}


def _floors(value: Any) -> int | None:
    """Rounded like the sync, same bounds as app/integrations/health/validation.py."""
    if isinstance(value, int | float) and 0 <= value <= 1000:
        return round(value)
    return None


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("daily_health", schema=None) as batch_op:
        batch_op.drop_column("floors_descended")
        batch_op.drop_column("floors_ascended")
