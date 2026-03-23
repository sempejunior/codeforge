from __future__ import annotations

from codeforge.domain.entities.repository import Repository, RepositoryStatus
from codeforge.domain.value_objects.project_id import ProjectId


def test_repository_create_sets_defaults() -> None:
    project_id = ProjectId.generate()

    repository = Repository.create(
        project_id=project_id,
        name="frontend-app",
        slug="acme/frontend-app",
        repo_url="https://github.com/acme/frontend-app",
    )

    assert repository.project_id == project_id
    assert repository.name == "frontend-app"
    assert repository.slug == "acme/frontend-app"
    assert repository.default_branch == "main"
    assert repository.status == RepositoryStatus.ACTIVE


def test_repository_archive_updates_status() -> None:
    repository = Repository.create(
        project_id=ProjectId.generate(),
        name="backend-api",
        slug="acme/backend-api",
        repo_url="https://github.com/acme/backend-api",
    )

    repository.archive()

    assert repository.status == RepositoryStatus.ARCHIVED
