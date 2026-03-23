from __future__ import annotations

import uuid
from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV


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
    database_path = tmp_path / "api.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), TempAsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        async_client._temp_dir = tmp_path
        yield async_client


@pytest.mark.asyncio
async def test_project_and_task_routes(client: AsyncClient) -> None:
    team_response = await client.post("/api/teams", json={"name": "Payments"})
    team_id = team_response.json()["id"]
    _make_git_repo(_tmp_dir(client), "backend")
    project_response = await client.post(
        "/api/projects",
        json={
            "name": "backend",
            "repo_url": "https://github.com/acme/backend",
            "team_id": team_id,
            "default_branch": "main",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()

    task_response = await client.post(
        "/api/tasks",
        json={
            "project_id": project["id"],
            "title": "Create PIX endpoint",
            "description": "Add route POST /payments/pix",
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()

    assign_response = await client.post(
        f"/api/tasks/{task['id']}/assign",
        json={"assignee_type": "ai"},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assignee_type"] == "ai"

    list_response = await client.get("/api/tasks", params={"team_id": team_id})
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [task["id"]]


@pytest.mark.asyncio
async def test_demand_story_sprint_routes(client: AsyncClient) -> None:
    _make_git_repo(_tmp_dir(client), "web")
    project_response = await client.post(
        "/api/projects",
        json={"name": "web", "repo_url": "https://github.com/acme/web", "default_branch": "main"},
    )
    project = project_response.json()

    demand_response = await client.post(
        "/api/demands",
        json={
            "title": "Checkout PIX",
            "business_objective": "Enable PIX checkout",
            "acceptance_criteria": ["Support QR code"],
            "linked_projects": [{"project_id": project["id"], "base_branch": "main"}],
        },
    )
    assert demand_response.status_code == 201
    demand = demand_response.json()

    story_response = await client.post(
        "/api/stories",
        json={
            "demand_id": demand["id"],
            "title": "PIX payment flow",
            "description": "Implement payment flow",
            "acceptance_criteria": ["Generate QR code"],
        },
    )
    assert story_response.status_code == 201
    story = story_response.json()

    sprint_response = await client.post(
        "/api/sprints",
        json={
            "name": "Sprint 1",
            "start_date": "2026-03-16",
            "end_date": "2026-03-30",
            "story_ids": [],
        },
    )
    assert sprint_response.status_code == 201
    sprint = sprint_response.json()

    add_story_response = await client.post(
        f"/api/stories/{story['id']}/add-to-sprint",
        json={"sprint_id": sprint["id"]},
    )
    assert add_story_response.status_code == 200
    assert add_story_response.json()["sprint_id"] == sprint["id"]


@pytest.mark.asyncio
async def test_transition_task_invalid_status_returns_422(client: AsyncClient) -> None:
    _make_git_repo(_tmp_dir(client), "p")
    project_resp = await client.post(
        "/api/projects",
        json={"name": "p", "repo_url": "https://github.com/acme/p", "default_branch": "main"},
    )
    project = project_resp.json()
    task_resp = await client.post(
        "/api/tasks",
        json={"project_id": project["id"], "title": "T", "description": "D"},
    )
    task = task_resp.json()

    resp = await client.post(
        f"/api/tasks/{task['id']}/transition",
        json={"status": "not_a_real_status"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_transition_task_invalid_state_machine_returns_422(client: AsyncClient) -> None:
    _make_git_repo(_tmp_dir(client), "p2")
    project_resp = await client.post(
        "/api/projects",
        json={"name": "p2", "repo_url": "https://github.com/acme/p2", "default_branch": "main"},
    )
    project = project_resp.json()
    task_resp = await client.post(
        "/api/tasks",
        json={"project_id": project["id"], "title": "T", "description": "D"},
    )
    task = task_resp.json()

    # PENDING → COMPLETED is not a valid transition
    resp = await client.post(
        f"/api/tasks/{task['id']}/transition",
        json={"status": "completed"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks_invalid_status_filter_returns_422(client: AsyncClient) -> None:
    _make_git_repo(_tmp_dir(client), "p3")
    project_resp = await client.post(
        "/api/projects",
        json={"name": "p3", "repo_url": "https://github.com/acme/p3", "default_branch": "main"},
    )
    project = project_resp.json()

    resp = await client.get("/api/tasks", params={"project_id": project["id"], "status": "bad"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agents_routes(client: AsyncClient) -> None:
    session_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    create_response = await client.post(
        "/api/agents",
        json={
            "id": session_id,
            "task_id": task_id,
            "agent_type": "coder",
            "model": "anthropic:claude-sonnet-4-20250514",
        },
    )
    assert create_response.status_code == 201

    get_response = await client.get(f"/api/agents/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == session_id

    list_response = await client.get("/api/agents", params={"task_id": task_id})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
