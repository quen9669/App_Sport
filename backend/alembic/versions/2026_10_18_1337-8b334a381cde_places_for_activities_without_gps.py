"""places for activities without gps

Revision ID: 8b334a381cde
Revises: 5974acb22aa2
Create Date: 2026-10-18 13:37:27.129321

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b334a381cde"
down_revision: str | Sequence[str] | None = "5974acb22aa2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The owner's gyms (decision 2026-10-18): strength sessions without GPS happen
# at Jims Gare, other activities without GPS at Jims Gasperich. Both can be
# changed in the app (map screen, "Mes lieux").
DEFAULT_PLACES = [
    ("Jims Gare", 49.600415, 6.131926, "strength_default"),
    ("Jims Gasperich", 49.587522, 6.120755, "other_default"),
]


def upgrade() -> None:
    """Upgrade schema."""
    place = op.create_table(
        "place",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place")),
        sa.UniqueConstraint("role", name=op.f("uq_place_role")),
    )
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.add_column(sa.Column("place_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_activity_place_id_place"),
            "place",
            ["place_id"],
            ["id"],
            ondelete="SET NULL",
        )
    now = datetime.now(UTC)
    op.bulk_insert(
        place,
        [
            {
                "name": name,
                "latitude": lat,
                "longitude": lng,
                "role": role,
                "created_at": now,
                "updated_at": now,
            }
            for name, lat, lng, role in DEFAULT_PLACES
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_activity_place_id_place"), type_="foreignkey")
        batch_op.drop_column("place_id")

    op.drop_table("place")
