from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class GitHubGatewayPort(ABC):
    @abstractmethod
    async def download_repository_archive(
        self,
        repo: str,
        ref: str,
        destination_dir: Path,
    ) -> Path: ...

    @abstractmethod
    async def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> str: ...

    @abstractmethod
    async def get_pull_request_status(self, pr_url: str) -> dict[str, Any]: ...
