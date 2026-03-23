from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app


@pytest.fixture
async def client(tmp_path):
    database_path = tmp_path / "api_team_documents.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def test_create_team_bootstraps_workspace(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Platform'})
    team_id = team_response.json()['id']

    workspace_response = await client.get(f'/api/team-documents/team/{team_id}')
    assert workspace_response.status_code == 200
    assert workspace_response.json()['documents'] == []


async def test_create_team_document_under_folder(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Growth'})
    team_id = team_response.json()['id']
    folder_response = await client.post(
        '/api/team-documents',
        json={
            'team_id': team_id,
            'title': 'Projetos',
            'kind': 'folder',
        },
    )
    projects_folder = folder_response.json()

    create_response = await client.post(
        '/api/team-documents',
        json={
            'team_id': team_id,
            'title': 'Contexto de integracoes',
            'kind': 'document',
            'parent_id': projects_folder['id'],
            'content': '# Integracoes',
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()['parent_id'] == projects_folder['id']
