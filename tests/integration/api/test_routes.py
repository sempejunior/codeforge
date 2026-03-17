from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app


@pytest.fixture
async def client(tmp_path):
    database_path = tmp_path / "api.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_project_and_task_routes(client: AsyncClient) -> None:
    project_response = await client.post(
        "/api/projects",
        json={"name": "backend", "path": "/tmp/backend", "default_branch": "main"},
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


@pytest.mark.asyncio
async def test_demand_story_sprint_routes(client: AsyncClient) -> None:
    project_response = await client.post(
        "/api/projects",
        json={"name": "web", "path": "/tmp/web", "default_branch": "main"},
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
