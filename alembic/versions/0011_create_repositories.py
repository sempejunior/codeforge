from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0011_create_repositories"
down_revision = "0010_story_technical_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("repo_url", sa.String(length=2048), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("local_path_hint", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    bind = op.get_bind()
    projects = bind.execute(
        sa.text(
            "SELECT id, name, repo_url, default_branch, created_at, updated_at FROM projects WHERE repo_url IS NOT NULL"
        )
    )
    for project in projects:
        slug = _derive_slug(project.repo_url, project.name)
        bind.execute(
            sa.text(
                "INSERT INTO repositories (id, project_id, name, slug, repo_url, default_branch, status, local_path_hint, created_at, updated_at) "
                "VALUES (:id, :project_id, :name, :slug, :repo_url, :default_branch, 'active', NULL, :created_at, :updated_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "project_id": project.id,
                "name": project.name,
                "slug": slug,
                "repo_url": project.repo_url,
                "default_branch": project.default_branch,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            },
        )


def downgrade() -> None:
    op.drop_table("repositories")


def _derive_slug(repo_url: str, fallback_name: str) -> str:
    candidate = repo_url.rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    if "/" in candidate:
        candidate = "/".join(candidate.split("/")[-2:])
    return candidate or fallback_name
