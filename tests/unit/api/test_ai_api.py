from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app


@pytest.fixture
async def client(tmp_path):
    database_path = tmp_path / "api_ai.db"
    fastapi_app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    async with fastapi_app.router.lifespan_context(fastapi_app), AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def test_inline_assist_returns_generated_text(client: AsyncClient) -> None:
    team_response = await client.post("/api/teams", json={"name": "Platform IA"})
    team_id = team_response.json()["id"]

    mock_result = AsyncMock()
    mock_result.content = "Texto melhorado"
    with patch(
        "codeforge.api.routers.ai.LiteLLMProvider.generate",
        AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/ai/inline-assist",
            json={
                "action": "improve",
                "text": "texto original",
                "team_id": team_id,
            },
        )

    assert response.status_code == 200
    assert response.json()["result"] == "Texto melhorado"


async def test_inline_assist_rejects_unknown_action(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ai/inline-assist",
        json={"action": "unknown", "text": "abc"},
    )

    assert response.status_code == 422
