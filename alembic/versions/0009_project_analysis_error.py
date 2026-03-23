from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_project_analysis_error"
down_revision = "0008_demand_generation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("analysis_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "analysis_error")
