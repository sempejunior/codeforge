from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WorktreeInfo:
    path: str
    branch: str
    task_id: str


class GitServicePort(ABC):
    @abstractmethod
    async def create_worktree(self, repo_path: str, task_id: str) -> WorktreeInfo: ...

    @abstractmethod
    async def remove_worktree(self, worktree_path: str) -> None: ...

    @abstractmethod
    async def commit(self, worktree_path: str, message: str) -> str: ...

    @abstractmethod
    async def create_branch(self, repo_path: str, branch_name: str) -> None: ...

    @abstractmethod
    async def merge(self, repo_path: str, branch_name: str) -> None: ...

    @abstractmethod
    async def get_current_branch(self, repo_path: str) -> str: ...

    @abstractmethod
    async def push_branch(
        self,
        repo_path: str,
        branch_name: str,
        remote: str = "origin",
    ) -> None: ...
