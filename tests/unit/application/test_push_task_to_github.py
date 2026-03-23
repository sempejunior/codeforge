from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.application.use_cases.push_task_to_github import push_task_to_github
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import Repository
from codeforge.domain.entities.task import Task
from codeforge.domain.ports.github_gateway import GitHubGatewayPort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.task_id import TaskId
from codeforge.infrastructure.git.git_service import GitService


class _TaskRepo(TaskRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Task] = []

    async def save(self, task: Task) -> None:
        self.saved.append(task)

    async def get_by_id(self, task_id: TaskId) -> Task | None:
        del task_id
        return None

    async def list_by_project(self, project_id: ProjectId, status=None) -> list[Task]:
        del project_id, status
        return []

    async def delete(self, task_id: TaskId) -> None:
        del task_id


class _Gateway(GitHubGatewayPort):
    async def download_repository_archive(
        self,
        repo: str,
        ref: str,
        destination_dir: Path,
    ) -> Path:
        del repo, ref, destination_dir
        raise NotImplementedError

    async def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> str:
        del repo, head_branch, base_branch, title, body
        return "https://github.com/acme/repo/pull/3"

    async def get_pull_request_status(self, pr_url: str) -> dict:
        del pr_url
        return {}


class _GitService(GitService):
    async def push_branch(self, repo_path: str, branch_name: str, remote: str = "origin") -> None:
        del repo_path, branch_name, remote

    async def get_remote_url(self, repo_path: str, remote: str = "origin") -> str:
        del repo_path, remote
        return "https://github.com/acme/repo.git"


@pytest.mark.asyncio
async def test_push_task_to_github_updates_task_with_pr_url() -> None:
    project = Project.create(name="api")
    repository = Repository.create(
        project_id=project.id,
        name="repo",
        slug="acme/repo",
        repo_url="https://github.com/acme/repo",
        default_branch="main",
    )
    task, _ = Task.create(project_id=project.id, title="Add login", description="- add endpoint")
    task.worktree_path = "/tmp/repo/.codeforge/worktrees/task-1"
    task.branch_name = "codeforge/task-1"
    task_repo = _TaskRepo()

    result = await push_task_to_github(
        task=task,
        repository=repository,
        task_repo=task_repo,
        github_gateway=_Gateway(),
        git_service=_GitService(),
        acceptance_criteria=["endpoint responds 200"],
    )

    assert result.pr_url == "https://github.com/acme/repo/pull/3"
    assert task.pr_url == "https://github.com/acme/repo/pull/3"
    assert task_repo.saved[-1].pr_url == "https://github.com/acme/repo/pull/3"
