from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_project_context_doc"
down_revision = "0003_task_pr_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("context_doc", sa.Text(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("analysis_status", sa.String(length=32), nullable=False, server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("projects", "analysis_status")
    op.drop_column("projects", "context_doc")
