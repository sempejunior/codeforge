from __future__ import annotations

from dataclasses import dataclass

from codeforge.domain.entities.repository import Repository
from codeforge.domain.entities.task import Task
from codeforge.domain.ports.github_gateway import GitHubGatewayPort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.infrastructure.config.workspace import resolve_repository_local_path
from codeforge.infrastructure.git.git_service import GitService


@dataclass
class PushTaskResult:
    pr_url: str
    compare_url: str


async def push_task_to_github(
    task: Task,
    repository: Repository,
    task_repo: TaskRepositoryPort,
    github_gateway: GitHubGatewayPort,
    git_service: GitService,
    acceptance_criteria: list[str],
) -> PushTaskResult:
    if not task.worktree_path:
        raise ValueError("Task does not have a worktree path")
    if not task.branch_name:
        raise ValueError("Task does not have a branch name")

    local_repo_path = resolve_repository_local_path(repository)
    if repository.repo_url:
        remote_ref = repository.repo_url
    elif local_repo_path:
        remote_ref = await git_service.get_remote_url(local_repo_path)
    else:
        raise ValueError("Repository could not be resolved locally")
    repo_slug = _resolve_repo_slug(remote_ref)
    await git_service.push_branch(task.worktree_path, task.branch_name)

    compare_url = (
        f"https://github.com/{repo_slug}/compare/{repository.default_branch}...{task.branch_name}"
    )
    body = _build_pr_body(task.description, acceptance_criteria, compare_url)
    title = task.title.strip() or f"Task {task.id}"
    pr_url = await github_gateway.create_pull_request(
        repo=repo_slug,
        head_branch=task.branch_name,
        base_branch=repository.default_branch,
        title=title,
        body=body,
    )
    task.pr_url = pr_url
    await task_repo.save(task)
    return PushTaskResult(pr_url=pr_url, compare_url=compare_url)


def _build_pr_body(description: str, acceptance_criteria: list[str], compare_url: str) -> str:
    criteria_lines = "\n".join(f"- {item}" for item in acceptance_criteria) or "- N/A"
    return (
        "## Task Description\n"
        f"{description.strip() or 'N/A'}\n\n"
        "## Acceptance Criteria\n"
        f"{criteria_lines}\n\n"
        "## Diff Summary\n"
        f"- Compare: {compare_url}\n"
    )


def _resolve_repo_slug(repo_reference: str) -> str:
    candidate = repo_reference.strip()
    if candidate.startswith("https://github.com/"):
        candidate = candidate.removeprefix("https://github.com/")
    if candidate.startswith("git@github.com:"):
        candidate = candidate.removeprefix("git@github.com:")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    candidate = candidate.strip("/")
    if candidate.count("/") != 1:
        raise ValueError("Could not resolve GitHub repository as owner/repo")
    owner, repo = candidate.split("/", maxsplit=1)
    if not owner or not repo:
        raise ValueError("Could not resolve GitHub repository as owner/repo")
    return f"{owner}/{repo}"
