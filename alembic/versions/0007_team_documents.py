from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_team_documents"
down_revision = "0006_story_linked_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("linked_project_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["linked_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["team_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("team_documents")
