from __future__ import annotations

import uuid
from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV

FAKE_ID = str(uuid.uuid4())


class TempAsyncClient(AsyncClient):
    _temp_dir: Path


def _make_git_repo(tmp_path, name: str) -> str:
    repo_path = tmp_path / name
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    return str(repo_path)


def _tmp_dir(client: AsyncClient) -> Path:
    return cast(Path, cast(TempAsyncClient, client)._temp_dir)


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_demands.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), TempAsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        async_client._temp_dir = tmp_path
        yield async_client


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    _make_git_repo(_tmp_dir(client), "test-demands")
    response = await client.post(
        "/api/projects",
        json={
            "name": "test-proj",
            "repo_url": "https://github.com/acme/test-demands",
            "default_branch": "main",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
async def demand_id(client: AsyncClient, project_id: str) -> str:
    response = await client.post(
        "/api/demands",
        json={
            "title": "Test Demand",
            "business_objective": "Test objective",
            "acceptance_criteria": ["AC1", "AC2"],
            "linked_projects": [{"project_id": project_id}],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_demand_with_linked_projects(
    client: AsyncClient, project_id: str
) -> None:
    response = await client.post(
        "/api/demands",
        json={
            "title": "New Demand",
            "business_objective": "Objective",
            "linked_projects": [{"project_id": project_id}],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Demand"
    assert len(data["linked_projects"]) == 1
    assert data["linked_projects"][0]["project_id"] == project_id
    assert data["generation_status"] == "none"
    assert data["generation_error"] is None


async def test_patch_demand_updates_title(
    client: AsyncClient, demand_id: str
) -> None:
    response = await client.patch(
        f"/api/demands/{demand_id}",
        json={"title": "Updated Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["business_objective"] == "Test objective"


async def test_patch_demand_updates_linked_projects(
    client: AsyncClient, demand_id: str
) -> None:
    _make_git_repo(_tmp_dir(client), "proj2")
    new_proj = await client.post(
        "/api/projects",
        json={
            "name": "proj2",
            "repo_url": "https://github.com/acme/proj2",
            "default_branch": "main",
        },
    )
    new_project_id = new_proj.json()["id"]

    response = await client.patch(
        f"/api/demands/{demand_id}",
        json={
            "linked_projects": [
                {"project_id": new_project_id, "base_branch": "develop"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["linked_projects"]) == 1
    assert data["linked_projects"][0]["project_id"] == new_project_id
    assert data["linked_projects"][0]["base_branch"] == "develop"


async def test_patch_demand_404_for_nonexistent(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/demands/{FAKE_ID}",
        json={"title": "X"},
    )
    assert response.status_code == 404


async def test_get_demand_includes_generation_status(
    client: AsyncClient, demand_id: str
) -> None:
    response = await client.get(f"/api/demands/{demand_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["generation_status"] == "none"
    assert data["generation_error"] is None


async def test_generate_stories_404_for_nonexistent(client: AsyncClient) -> None:
    response = await client.post(f"/api/demands/{FAKE_ID}/generate-stories")
    assert response.status_code == 404


async def test_generate_stories_422_for_no_linked_projects(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/demands",
        json={
            "title": "Empty Demand",
            "business_objective": "No projects",
            "linked_projects": [],
        },
    )
    demand_id = response.json()["id"]

    response = await client.post(f"/api/demands/{demand_id}/generate-stories")
    assert response.status_code == 422


async def test_generation_stream_404_for_nonexistent(client: AsyncClient) -> None:
    response = await client.get(f"/api/demands/{FAKE_ID}/generation-stream")
    assert response.status_code == 404


async def test_list_demands_returns_all(
    client: AsyncClient, demand_id: str
) -> None:
    response = await client.get("/api/demands")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    ids = [d["id"] for d in data]
    assert demand_id in ids


async def test_list_demands_filters_by_team(client: AsyncClient, project_id: str) -> None:
    team_response = await client.post("/api/teams", json={"name": "Team A"})
    team_id = team_response.json()["id"]
    demand_response = await client.post(
        "/api/demands",
        json={
            "title": "Team demand",
            "business_objective": "Scoped objective",
            "team_id": team_id,
            "linked_projects": [{"project_id": project_id}],
        },
    )
    demand_id = demand_response.json()["id"]

    unscoped_response = await client.post(
        "/api/demands",
        json={
            "title": "Other demand",
            "business_objective": "Other objective",
            "linked_projects": [{"project_id": project_id}],
        },
    )
    assert unscoped_response.status_code == 201

    response = await client.get("/api/demands", params={"team_id": team_id})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [demand_id]


async def test_delete_demand_removes_record(client: AsyncClient, demand_id: str) -> None:
    response = await client.delete(f"/api/demands/{demand_id}")

    assert response.status_code == 204
    get_response = await client.get(f"/api/demands/{demand_id}")
    assert get_response.status_code == 404
