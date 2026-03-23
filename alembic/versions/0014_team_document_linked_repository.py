from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_team_document_linked_repository"
down_revision = "0013_project_repository_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("team_documents") as batch_op:
        batch_op.add_column(
            sa.Column("linked_repository_id", sa.String(36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_team_documents_linked_repository_id",
            "repositories",
            ["linked_repository_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("team_documents") as batch_op:
        batch_op.drop_constraint(
            "fk_team_documents_linked_repository_id", type_="foreignkey"
        )
        batch_op.drop_column("linked_repository_id")
