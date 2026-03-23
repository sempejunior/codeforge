from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_story_linked_projects"
down_revision = "0005_teams_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column("linked_projects", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("stories", "linked_projects")
