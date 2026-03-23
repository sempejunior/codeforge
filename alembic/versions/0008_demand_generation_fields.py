from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_demand_generation_fields"
down_revision = "0007_team_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "demands",
        sa.Column(
            "generation_status",
            sa.String(length=64),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "demands",
        sa.Column("generation_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("demands", "generation_error")
    op.drop_column("demands", "generation_status")
