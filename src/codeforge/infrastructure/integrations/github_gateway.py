from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zipfile import ZipFile

import httpx

from codeforge.domain.ports.github_gateway import GitHubGatewayPort
from codeforge.infrastructure.integrations.github_app import create_installation_token


class GitHubGateway(GitHubGatewayPort):
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._token = token or os.getenv("GITHUB_TOKEN")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def download_repository_archive(
        self,
        repo: str,
        ref: str,
        destination_dir: Path,
    ) -> Path:
        response = await self._request(
            "GET",
            f"{self._base_url}/repos/{repo}/zipball/{ref}",
        )
        archive_dir = destination_dir / repo.replace("/", "__")
        archive_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(BytesIO(response.content)) as archive:
            archive.extractall(archive_dir)

        extracted_entries = [entry for entry in archive_dir.iterdir() if entry.is_dir()]
        if len(extracted_entries) == 1:
            return extracted_entries[0]
        return archive_dir

    async def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> str:
        self._require_token()
        url = f"{self._base_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
        }
        response = await self._request("POST", url, json=payload)
        data = response.json()
        html_url = data.get("html_url")
        if not isinstance(html_url, str) or not html_url:
            raise RuntimeError("GitHub API did not return pull request URL")
        return html_url

    async def get_pull_request_status(self, pr_url: str) -> dict[str, Any]:
        owner, repo, number = _parse_pr_url(pr_url)
        pr_data = await self._request_json(
            "GET",
            f"{self._base_url}/repos/{owner}/{repo}/pulls/{number}",
        )
        checks_data = await self._request_json(
            "GET",
            f"{self._base_url}/repos/{owner}/{repo}/commits/{pr_data['head']['sha']}/status",
        )
        checks_passing = checks_data.get("state") == "success"
        return {
            "state": pr_data.get("state", "open"),
            "merged": bool(pr_data.get("merged", False)),
            "checks_passing": checks_passing,
            "head_sha": pr_data["head"]["sha"],
            "base_ref": pr_data["base"]["ref"],
            "head_ref": pr_data["head"]["ref"],
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._request(method, url, json=json)
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("GitHub API response is not a JSON object")
        return data

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        token = self._token
        repo_slug = _extract_repo_slug_from_api_url(url)
        if token is None and repo_slug is not None:
            try:
                token = await create_installation_token(repo_slug)
            except Exception:
                token = self._token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.request(method=method, url=url, headers=headers, json=json)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub API error ({response.status_code}): {response.text}")
        return response

    def _require_token(self) -> None:
        if not self._token:
            raise ValueError("GITHUB_TOKEN is required to use GitHub gateway")


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    parsed = urlparse(pr_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 4 or path_parts[2] != "pull":
        raise ValueError(f"Invalid GitHub pull request URL: {pr_url}")
    owner, repo, _, number_raw = path_parts[:4]
    return owner, repo, int(number_raw)


def _extract_repo_slug_from_api_url(url: str) -> str | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "repos":
        return f"{parts[1]}/{parts[2]}"
    return None
