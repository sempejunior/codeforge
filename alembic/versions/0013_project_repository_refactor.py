from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_project_repository_refactor"
down_revision = "0012_story_project_and_repositories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("path", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("context_doc", sa.Text(), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("analysis_status", sa.String(length=32), nullable=False, server_default="none"),
    )
    op.add_column(
        "repositories",
        sa.Column("analysis_executor", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("analysis_error", sa.Text(), nullable=True),
    )

    bind = op.get_bind()
    projects = bind.execute(
        sa.text(
            "SELECT id, path, context_doc, analysis_status, analysis_executor, analysis_error "
            "FROM projects"
        )
    )
    for project in projects:
        bind.execute(
            sa.text(
                "UPDATE repositories SET "
                "path = :path, "
                "context_doc = :context_doc, "
                "analysis_status = :analysis_status, "
                "analysis_executor = :analysis_executor, "
                "analysis_error = :analysis_error "
                "WHERE project_id = :project_id"
            ),
            {
                "path": project.path,
                "context_doc": project.context_doc,
                "analysis_status": project.analysis_status or "none",
                "analysis_executor": project.analysis_executor,
                "analysis_error": project.analysis_error,
                "project_id": project.id,
            },
        )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("path")
        batch_op.drop_column("repo_url")
        batch_op.drop_column("default_branch")
        batch_op.drop_column("context_doc")
        batch_op.drop_column("analysis_status")
        batch_op.drop_column("analysis_executor")
        batch_op.drop_column("analysis_error")


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("path", sa.String(length=1024), nullable=True),
        )
        batch_op.add_column(
            sa.Column("repo_url", sa.String(length=2048), nullable=True),
        )
        batch_op.add_column(
            sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        )
        batch_op.add_column(
            sa.Column("context_doc", sa.Text(), nullable=True),
        )
        batch_op.add_column(
            sa.Column("analysis_status", sa.String(length=32), nullable=False, server_default="none"),
        )
        batch_op.add_column(
            sa.Column("analysis_executor", sa.String(length=255), nullable=True),
        )
        batch_op.add_column(
            sa.Column("analysis_error", sa.Text(), nullable=True),
        )

    bind = op.get_bind()
    repos = bind.execute(
        sa.text(
            "SELECT project_id, repo_url, default_branch, path, context_doc, "
            "analysis_status, analysis_executor, analysis_error "
            "FROM repositories"
        )
    )
    for repo in repos:
        bind.execute(
            sa.text(
                "UPDATE projects SET "
                "path = :path, "
                "repo_url = :repo_url, "
                "default_branch = :default_branch, "
                "context_doc = :context_doc, "
                "analysis_status = :analysis_status, "
                "analysis_executor = :analysis_executor, "
                "analysis_error = :analysis_error "
                "WHERE id = :project_id"
            ),
            {
                "path": repo.path,
                "repo_url": repo.repo_url,
                "default_branch": repo.default_branch,
                "context_doc": repo.context_doc,
                "analysis_status": repo.analysis_status,
                "analysis_executor": repo.analysis_executor,
                "analysis_error": repo.analysis_error,
                "project_id": repo.project_id,
            },
        )

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_column("analysis_error")
        batch_op.drop_column("analysis_executor")
        batch_op.drop_column("analysis_status")
        batch_op.drop_column("context_doc")
        batch_op.drop_column("path")
