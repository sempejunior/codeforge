from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV

FAKE_PROJECT_ID = str(uuid.uuid4())
FAKE_REPO_ID = str(uuid.uuid4())


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_analysis.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.fixture
async def project_and_repo(client: AsyncClient) -> tuple[str, str]:
    project_response = await client.post(
        "/api/projects",
        json={"name": "test-analysis"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    repo_response = await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "test-analysis",
            "slug": "acme/test-analysis",
            "repo_url": "https://github.com/acme/test-analysis",
            "default_branch": "main",
        },
    )
    assert repo_response.status_code == 201
    repository_id = repo_response.json()["id"]

    return project_id, repository_id


async def test_analyze_returns_404_for_nonexistent_repository(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/projects/{FAKE_PROJECT_ID}/repositories/{FAKE_REPO_ID}/analyze"
    )
    assert response.status_code == 404


async def test_analysis_status_returns_none_for_new_repository(
    client: AsyncClient, project_and_repo: tuple[str, str]
) -> None:
    project_id, repository_id = project_and_repo
    response = await client.get(
        f"/api/projects/{project_id}/repositories/{repository_id}/analysis-status"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_status"] == "none"
    assert data["context_doc"] is None


async def test_repository_response_includes_analysis_fields(
    client: AsyncClient, project_and_repo: tuple[str, str]
) -> None:
    project_id, repository_id = project_and_repo
    response = await client.get(
        f"/api/projects/{project_id}/repositories/{repository_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_status"] == "none"
    assert data["context_doc"] is None


async def test_project_response_does_not_include_analysis_fields(
    client: AsyncClient, project_and_repo: tuple[str, str]
) -> None:
    project_id, _ = project_and_repo
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert "analysis_status" not in data
    assert "context_doc" not in data
    assert "repo_url" not in data


async def test_analysis_status_returns_error_message_when_remote_access_fails(
    client: AsyncClient,
    project_and_repo: tuple[str, str],
) -> None:
    project_id, repository_id = project_and_repo
    with patch(
        "codeforge.application.use_cases.run_repository_analysis.GitHubGateway.download_repository_archive",
        AsyncMock(side_effect=RuntimeError("GitHub API error (401): unauthorized")),
    ):
        trigger_response = await client.post(
            f"/api/projects/{project_id}/repositories/{repository_id}/analyze"
        )
        assert trigger_response.status_code == 200

        data = {"analysis_status": "none", "analysis_error": None}
        for _ in range(10):
            status_response = await client.get(
                f"/api/projects/{project_id}/repositories/{repository_id}/analysis-status"
            )
            data = status_response.json()
            if data["analysis_status"] == "error":
                break

    assert data["analysis_status"] == "error"
    assert "GitHub App" in data["analysis_error"]


async def test_analysis_status_returns_404_for_nonexistent_repository(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/api/projects/{FAKE_PROJECT_ID}/repositories/{FAKE_REPO_ID}/analysis-status"
    )
    assert response.status_code == 404


async def test_skills_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for skill in data:
        assert "name" in skill
        assert "available" in skill
        assert "missing" in skill
