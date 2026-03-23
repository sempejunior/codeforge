from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from codeforge.api.app import create_app

PRIVATE_KEY_PLACEHOLDER = "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----"


@pytest.fixture
async def client(tmp_path):
    database_path = tmp_path / "api_settings.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{database_path}")
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


async def test_get_github_app_status_returns_install_url(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_SLUG", "codeforge-test")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", PRIVATE_KEY_PLACEHOLDER)

    response = await client.get("/api/settings/github-app")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["install_url"] == "https://github.com/apps/codeforge-test/installations/new"


async def test_get_github_app_repository_access_returns_status(client: AsyncClient) -> None:
    with patch(
        "codeforge.api.routers.settings.get_repository_access",
        AsyncMock(return_value=type("Access", (), {
            "configured": True,
            "repo_slug": "acme/backend",
            "accessible": False,
            "reason": "repository_not_authorized",
            "install_url": "https://github.com/apps/codeforge/installations/new",
        })()),
    ):
        response = await client.get(
            "/api/settings/github-app/repository-access",
            params={"repo_url": "https://github.com/acme/backend"},
        )

    assert response.status_code == 200
    assert response.json()["reason"] == "repository_not_authorized"
