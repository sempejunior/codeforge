from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_projects.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def test_create_project_requires_name(client: AsyncClient) -> None:
    response = await client.post(
        "/api/projects",
        json={},
    )
    assert response.status_code == 422


async def test_create_project_with_name_only(client: AsyncClient) -> None:
    response = await client.post(
        "/api/projects",
        json={"name": "backend"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "backend"
    assert data["team_id"] is None
    assert "repo_url" not in data
    assert "path" not in data
    assert "analysis_status" not in data


async def test_create_project_rejects_nonexistent_team(client: AsyncClient) -> None:
    response = await client.post(
        "/api/projects",
        json={"name": "backend", "team_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


async def test_patch_project_updates_name(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/projects",
        json={"name": "backend"},
    )
    project_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "backend-v2"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "backend-v2"


async def test_delete_project_rejects_when_linked_to_active_demand(
    client: AsyncClient,
) -> None:
    project_response = await client.post(
        "/api/projects",
        json={"name": "backend"},
    )
    project_id = project_response.json()["id"]

    demand_response = await client.post(
        "/api/demands",
        json={
            "title": "Protected demand",
            "business_objective": "Keep project linked",
            "linked_projects": [{"project_id": project_id}],
        },
    )
    assert demand_response.status_code == 201

    response = await client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Project linked to active demands cannot be deleted"


async def test_delete_project_removes_existing_project(client: AsyncClient) -> None:
    project_response = await client.post(
        "/api/projects",
        json={"name": "backend"},
    )
    project_id = project_response.json()["id"]

    response = await client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 204
    get_response = await client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 404
