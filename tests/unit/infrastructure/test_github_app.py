from __future__ import annotations

import pytest

from codeforge.infrastructure.integrations.github_app import build_app_jwt, load_github_app_settings

PRIVATE_KEY_PLACEHOLDER = "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----"


def test_load_github_app_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_SLUG", "codeforge-test")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", PRIVATE_KEY_PLACEHOLDER)

    settings = load_github_app_settings()

    assert settings.app_id == "123"
    assert settings.slug == "codeforge-test"
    assert "\n" in settings.private_key
    assert settings.install_url == "https://github.com/apps/codeforge-test/installations/new"


def test_build_app_jwt_requires_configured_settings() -> None:
    with pytest.raises(ValueError):
        build_app_jwt(load_github_app_settings())
