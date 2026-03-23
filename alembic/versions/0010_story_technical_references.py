from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_story_technical_references"
down_revision = "0009_project_analysis_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column(
            "technical_references",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("stories", "technical_references")
