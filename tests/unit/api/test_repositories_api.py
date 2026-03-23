from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_repositories.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    response = await client.post(
        "/api/projects",
        json={"name": "payments-platform"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_repository_for_project(
    client: AsyncClient, project_id: str
) -> None:
    response = await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-api",
            "slug": "acme/payments-api",
            "repo_url": "https://github.com/acme/payments-api",
            "default_branch": "main",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["repo_url"] == "https://github.com/acme/payments-api"
    assert data["analysis_status"] == "none"


async def test_list_repositories_for_project(
    client: AsyncClient, project_id: str
) -> None:
    await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-api",
            "slug": "acme/payments-api",
            "repo_url": "https://github.com/acme/payments-api",
            "default_branch": "main",
        },
    )

    response = await client.get(f"/api/projects/{project_id}/repositories")

    assert response.status_code == 200
    repositories = response.json()
    assert len(repositories) == 1
    assert repositories[0]["repo_url"] == "https://github.com/acme/payments-api"


async def test_create_additional_repository_for_project(
    client: AsyncClient, project_id: str
) -> None:
    await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-api",
            "slug": "acme/payments-api",
            "repo_url": "https://github.com/acme/payments-api",
            "default_branch": "main",
        },
    )

    response = await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-web",
            "slug": "acme/payments-web",
            "repo_url": "https://github.com/acme/payments-web",
            "default_branch": "main",
        },
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == project_id

    list_response = await client.get(f"/api/projects/{project_id}/repositories")
    assert len(list_response.json()) == 2


async def test_reject_duplicate_repository_url(
    client: AsyncClient, project_id: str
) -> None:
    await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-api",
            "slug": "acme/payments-api",
            "repo_url": "https://github.com/acme/payments-api",
            "default_branch": "main",
        },
    )

    response = await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "payments-api-copy",
            "slug": "acme/payments-api-copy",
            "repo_url": "https://github.com/acme/payments-api",
            "default_branch": "main",
        },
    )

    assert response.status_code == 409
