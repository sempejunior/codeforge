from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from codeforge.infrastructure.integrations.github_gateway import GitHubGateway


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict | None,
        text: str = "",
        content: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = content

    def json(self) -> dict:
        return self._payload or {}


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    async def request(self, method: str, url: str, headers: dict, json: dict | None = None):
        del method, url, headers, json
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_create_pull_request_returns_html_url(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_FakeResponse(201, {"html_url": "https://github.com/o/r/pull/1"})]
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: _FakeClient(responses))

    gateway = GitHubGateway(token="token")
    pr_url = await gateway.create_pull_request(
        repo="o/r",
        head_branch="feature",
        base_branch="main",
        title="Title",
        body="Body",
    )

    assert pr_url == "https://github.com/o/r/pull/1"


@pytest.mark.asyncio
async def test_get_pull_request_status_returns_state_and_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        _FakeResponse(
            200,
            {
                "state": "open",
                "merged": False,
                "head": {"sha": "abc", "ref": "feature"},
                "base": {"ref": "main"},
            },
        ),
        _FakeResponse(200, {"state": "success"}),
    ]
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: _FakeClient(responses))

    gateway = GitHubGateway(token="token")
    status = await gateway.get_pull_request_status("https://github.com/o/r/pull/2")

    assert status["state"] == "open"
    assert status["checks_passing"] is True


@pytest.mark.asyncio
async def test_download_repository_archive_extracts_zip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "repo.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("acme-repo-123/README.md", "hello")

    responses = [
        _FakeResponse(200, None, content=archive_path.read_bytes()),
    ]
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: _FakeClient(responses))

    gateway = GitHubGateway()
    extracted = await gateway.download_repository_archive(
        repo="acme/repo",
        ref="main",
        destination_dir=tmp_path / "extract",
    )

    assert (extracted / "README.md").read_text() == "hello"
