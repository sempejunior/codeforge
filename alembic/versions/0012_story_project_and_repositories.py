from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_story_project_and_repositories"
down_revision = "0011_create_repositories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stories") as batch_op:
        batch_op.add_column(
            sa.Column("project_id", sa.String(length=36), nullable=True),
        )
        batch_op.add_column(
            sa.Column("repository_ids", sa.JSON(), nullable=False, server_default="[]"),
        )
        batch_op.create_foreign_key(
            "fk_stories_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("stories") as batch_op:
        batch_op.drop_constraint("fk_stories_project_id_projects", type_="foreignkey")
        batch_op.drop_column("repository_ids")
        batch_op.drop_column("project_id")
