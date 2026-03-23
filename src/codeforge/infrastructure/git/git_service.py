from __future__ import annotations

import asyncio
from pathlib import Path

from codeforge.domain.ports.git_service import GitServicePort, WorktreeInfo


class GitService(GitServicePort):
    async def create_worktree(self, repo_path: str, task_id: str) -> WorktreeInfo:
        repo = Path(repo_path).resolve()
        branch = f"codeforge/task-{task_id}"
        worktree_path = repo / ".codeforge" / "worktrees" / f"task-{task_id}"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        await _run_git(repo, "worktree", "add", "-B", branch, str(worktree_path))
        return WorktreeInfo(path=str(worktree_path), branch=branch, task_id=task_id)

    async def remove_worktree(self, worktree_path: str) -> None:
        target = Path(worktree_path).resolve()
        branch = await self.get_current_branch(str(target))
        repo_root = await _resolve_main_repo(target)
        await _run_git(repo_root, "worktree", "remove", "--force", str(target))
        await _run_git(repo_root, "worktree", "prune")
        if branch:
            await _run_git(repo_root, "branch", "-D", branch)

    async def commit(self, worktree_path: str, message: str) -> str:
        worktree = Path(worktree_path).resolve()
        await _run_git(worktree, "add", "-A")
        await _run_git(worktree, "commit", "-m", message)
        return (await _run_git(worktree, "rev-parse", "HEAD")).strip()

    async def create_branch(self, repo_path: str, branch_name: str) -> None:
        repo = Path(repo_path).resolve()
        await _run_git(repo, "checkout", "-b", branch_name)

    async def merge(self, repo_path: str, branch_name: str) -> None:
        repo = Path(repo_path).resolve()
        await _run_git(repo, "merge", "--no-ff", branch_name)

    async def get_current_branch(self, repo_path: str) -> str:
        repo = Path(repo_path).resolve()
        return (await _run_git(repo, "branch", "--show-current")).strip()

    async def push_branch(self, repo_path: str, branch_name: str, remote: str = "origin") -> None:
        repo = Path(repo_path).resolve()
        await _run_git(repo, "push", "-u", remote, branch_name)

    async def get_remote_url(self, repo_path: str, remote: str = "origin") -> str:
        repo = Path(repo_path).resolve()
        return (await _run_git(repo, "remote", "get-url", remote)).strip()

    async def get_diff(self, worktree_path: str, base_branch: str) -> str:
        worktree = Path(worktree_path).resolve()
        return await _run_git(worktree, "diff", f"{base_branch}...HEAD")

    async def get_changed_files(self, worktree_path: str, base_branch: str) -> list[str]:
        worktree = Path(worktree_path).resolve()
        output = await _run_git(worktree, "diff", "--name-only", f"{base_branch}...HEAD")
        return [line for line in output.splitlines() if line.strip()]


async def _resolve_main_repo(worktree_path: Path) -> Path:
    output = await _run_git(worktree_path, "rev-parse", "--git-common-dir")
    common_dir = Path(output.strip())
    if not common_dir.is_absolute():
        common_dir = (worktree_path / common_dir).resolve()
    return common_dir.parent


async def _run_git(repo_path: Path, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_path),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(stderr_text.strip() or stdout_text.strip())
    return stdout_text
