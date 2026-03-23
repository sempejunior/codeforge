from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_teams.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def test_create_and_list_teams(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/teams",
        json={"name": "Platform", "description": "Shared ownership"},
    )

    assert create_response.status_code == 201
    team = create_response.json()
    assert team["name"] == "Platform"
    assert team["description"] == "Shared ownership"

    list_response = await client.get("/api/teams")
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["id"] == team["id"]


async def test_create_project_with_team_id(client: AsyncClient) -> None:
    team_response = await client.post("/api/teams", json={"name": "Payments"})
    team_id = team_response.json()["id"]

    response = await client.post(
        "/api/projects",
        json={
            "name": "checkout-api",
            "team_id": team_id,
        },
    )

    assert response.status_code == 201
    assert response.json()["team_id"] == team_id


async def test_create_demand_with_team_id(client: AsyncClient) -> None:
    team_response = await client.post("/api/teams", json={"name": "Growth"})
    team_id = team_response.json()["id"]

    response = await client.post(
        "/api/demands",
        json={
            "title": "Launch referral flow",
            "business_objective": "Increase acquisition",
            "team_id": team_id,
            "linked_projects": [],
        },
    )

    assert response.status_code == 201
    assert response.json()["team_id"] == team_id


async def test_get_team_context_reports_project_readiness(client: AsyncClient) -> None:
    team_response = await client.post("/api/teams", json={"name": "Core"})
    team_id = team_response.json()["id"]

    project_response = await client.post(
        "/api/projects",
        json={
            "name": "core-api",
            "team_id": team_id,
        },
    )
    project_id = project_response.json()["id"]

    repo_response = await client.post(
        f"/api/projects/{project_id}/repositories",
        json={
            "name": "core-api",
            "slug": "acme/core-api",
            "repo_url": "https://github.com/acme/core-api",
            "default_branch": "main",
        },
    )
    assert repo_response.status_code == 201

    context_response = await client.get(f"/api/teams/{team_id}/context")
    assert context_response.status_code == 200

    data = context_response.json()
    assert data["team_id"] == team_id
    assert data["total_repositories"] == 1
    assert data["missing_context_repositories"] == 1
    assert data["repositories"][0]["project_id"] == project_id
    assert data["repositories"][0]["source_label"] == "repo"


async def test_create_project_bootstraps_project_folder(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Core Docs'})
    team_id = team_response.json()['id']

    project_response = await client.post(
        '/api/projects',
        json={
            'name': 'core-api',
            'team_id': team_id,
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()['id']

    workspace_response = await client.get(f'/api/team-documents/team/{team_id}')
    assert workspace_response.status_code == 200
    docs = workspace_response.json()['documents']
    assert len(docs) == 1
    folder = docs[0]
    assert folder['kind'] == 'folder'
    assert folder['title'] == 'core-api'
    assert folder['linked_project_id'] == project_id
    assert folder['source'] == 'system'
    assert folder['parent_id'] is None


async def test_get_generation_context_returns_projects_and_workspace_docs(
    client: AsyncClient,
) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Context Team'})
    team_id = team_response.json()['id']
    project_response = await client.post(
        '/api/projects',
        json={
            'name': 'context-repo',
            'team_id': team_id,
        },
    )
    project_id = project_response.json()['id']

    await client.post(
        f'/api/projects/{project_id}/repositories',
        json={
            'name': 'context-repo',
            'slug': 'acme/context-repo',
            'repo_url': 'https://github.com/acme/context-repo',
            'default_branch': 'main',
        },
    )

    demand_response = await client.post(
        '/api/demands',
        json={
            'title': 'Demand',
            'business_objective': 'Objective',
            'team_id': team_id,
            'linked_projects': [{'project_id': project_id}],
        },
    )
    demand_id = demand_response.json()['id']

    folder_response = await client.post(
        '/api/team-documents',
        json={'team_id': team_id, 'title': 'Produto', 'kind': 'folder'},
    )
    folder_id = folder_response.json()['id']
    doc_response = await client.post(
        '/api/team-documents',
        json={
            'team_id': team_id,
            'title': 'PRD PIX',
            'kind': 'document',
            'parent_id': folder_id,
            'content': 'Checkout PIX with explicit product rules',
        },
    )

    response = await client.get(
        f'/api/teams/{team_id}/generation-context',
        params={'demand_id': demand_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['selected_project_ids'] == [project_id]
    assert doc_response.json()['id'] in data['selected_document_ids']
    assert any(item['kind'] == 'project_context' for item in data['items'])
    assert any(item['kind'] == 'workspace_document' for item in data['items'])
