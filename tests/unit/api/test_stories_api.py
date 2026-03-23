from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app
from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV


@pytest.fixture
async def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "api_stories.db"
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(tmp_path))
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    fastapi_app.state.temp_dir = tmp_path
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def _create_project_with_repo(
    client: AsyncClient, team_id: str, name: str
) -> tuple[str, str]:
    project_response = await client.post(
        '/api/projects',
        json={'name': name, 'team_id': team_id},
    )
    project_id = project_response.json()['id']

    repo_response = await client.post(
        f'/api/projects/{project_id}/repositories',
        json={
            'name': name,
            'slug': f'acme/{name}',
            'repo_url': f'https://github.com/acme/{name}',
            'default_branch': 'main',
        },
    )
    repository_id = repo_response.json()['id']
    return project_id, repository_id


async def test_create_story_with_linked_projects(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Platform'})
    team_id = team_response.json()['id']

    project_id, repository_id = await _create_project_with_repo(client, team_id, 'backend')

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

    response = await client.post(
        '/api/stories',
        json={
            'demand_id': demand_id,
            'title': 'Story',
            'description': 'Description',
            'project_id': project_id,
            'repository_ids': [repository_id],
            'acceptance_criteria': ['AC1'],
            'technical_references': ['payments.py', 'PaymentService'],
            'linked_projects': [project_id],
        },
    )

    assert response.status_code == 201
    assert response.json()['project_id'] == project_id
    assert response.json()['repository_ids'] == [repository_id]
    assert response.json()['linked_projects'] == [project_id]
    assert response.json()['technical_references'] == ['payments.py', 'PaymentService']


async def test_patch_story_updates_content(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Platform Patch'})
    team_id = team_response.json()['id']

    project_id, repository_id = await _create_project_with_repo(client, team_id, 'backend-patch')

    demand_response = await client.post(
        '/api/demands',
        json={
            'title': 'Demand',
            'business_objective': 'Objective',
            'team_id': team_id,
            'linked_projects': [{'project_id': project_id}],
        },
    )
    story_response = await client.post(
        '/api/stories',
        json={
            'demand_id': demand_response.json()['id'],
            'title': 'Story',
            'description': 'Description',
            'project_id': project_id,
            'repository_ids': [repository_id],
            'acceptance_criteria': ['AC1'],
            'linked_projects': [project_id],
        },
    )
    story_id = story_response.json()['id']

    response = await client.patch(
        f'/api/stories/{story_id}',
        json={
            'title': 'Story updated',
            'description': 'Updated description',
            'project_id': project_id,
            'repository_ids': [repository_id],
            'acceptance_criteria': ['AC2'],
            'technical_references': ['payments.py'],
        },
    )

    assert response.status_code == 200
    assert response.json()['title'] == 'Story updated'
    assert response.json()['description'] == 'Updated description'
    assert response.json()['acceptance_criteria'] == ['AC2']
    assert response.json()['technical_references'] == ['payments.py']
    assert response.json()['repository_ids'] == [repository_id]


async def test_delete_story_removes_record(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Platform Delete'})
    team_id = team_response.json()['id']

    project_response = await client.post(
        '/api/projects',
        json={'name': 'backend', 'team_id': team_id},
    )
    project_id = project_response.json()['id']

    demand_response = await client.post(
        '/api/demands',
        json={
            'title': 'Demand',
            'business_objective': 'Objective',
            'team_id': team_id,
            'linked_projects': [{'project_id': project_id}],
        },
    )
    story_response = await client.post(
        '/api/stories',
        json={
            'demand_id': demand_response.json()['id'],
            'title': 'Story',
            'description': 'Description',
            'linked_projects': [project_id],
        },
    )
    story_id = story_response.json()['id']

    response = await client.delete(f'/api/stories/{story_id}')

    assert response.status_code == 204
    get_response = await client.get(f'/api/stories/{story_id}')
    assert get_response.status_code == 404


async def test_create_story_rejects_repository_outside_project(client: AsyncClient) -> None:
    team_response = await client.post('/api/teams', json={'name': 'Platform Scope'})
    team_id = team_response.json()['id']

    project_a_id, _ = await _create_project_with_repo(client, team_id, 'backend-scope')
    project_b_id, foreign_repository_id = await _create_project_with_repo(
        client, team_id, 'frontend-scope'
    )

    demand_response = await client.post(
        '/api/demands',
        json={
            'title': 'Demand',
            'business_objective': 'Objective',
            'team_id': team_id,
            'linked_projects': [{'project_id': project_a_id}, {'project_id': project_b_id}],
        },
    )

    response = await client.post(
        '/api/stories',
        json={
            'demand_id': demand_response.json()['id'],
            'project_id': project_a_id,
            'repository_ids': [foreign_repository_id],
            'title': 'Scoped story',
            'description': 'Description',
            'linked_projects': [project_a_id, project_b_id],
        },
    )

    assert response.status_code == 422
    assert response.json()['detail'] == 'Repository not linked to the selected project'
