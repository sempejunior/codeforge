from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IssueData:
    title: str
    body: str
    url: str
    source_ref: str


class IntegrationGatewayPort(ABC):
    @abstractmethod
    async def fetch_github_issue(
        self, owner: str, repo: str, issue_number: int
    ) -> IssueData: ...

    @abstractmethod
    async def fetch_jira_epic(self, issue_key: str) -> IssueData: ...

    @abstractmethod
    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> str: ...
