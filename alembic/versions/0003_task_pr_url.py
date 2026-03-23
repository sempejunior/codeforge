from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_task_pr_url"
down_revision = "0002_agent_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("pr_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "pr_url")
