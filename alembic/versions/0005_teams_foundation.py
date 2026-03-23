from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_teams_foundation"
down_revision = "0004_project_context_doc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("team_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("analysis_executor", sa.String(length=255), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_projects_team_id",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("demands") as batch_op:
        batch_op.add_column(sa.Column("team_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_demands_team_id",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("demands") as batch_op:
        batch_op.drop_constraint("fk_demands_team_id", type_="foreignkey")
        batch_op.drop_column("team_id")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_team_id", type_="foreignkey")
        batch_op.drop_column("analysis_executor")
        batch_op.drop_column("team_id")

    op.drop_table("teams")
