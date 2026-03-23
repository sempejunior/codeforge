from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx
import jwt


@dataclass(frozen=True)
class GitHubAppSettings:
    app_id: str | None
    slug: str | None
    private_key: str | None
    base_url: str = "https://github.com"
    api_base_url: str = "https://api.github.com"

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.slug and self.private_key)

    @property
    def install_url(self) -> str | None:
        if not self.slug:
            return None
        return f"{self.base_url.rstrip('/')}/apps/{self.slug}/installations/new"


@dataclass(frozen=True)
class GitHubAppRepositoryAccess:
    configured: bool
    repo_slug: str | None
    accessible: bool
    reason: str
    install_url: str | None


def load_github_app_settings() -> GitHubAppSettings:
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    if private_key and "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")
    return GitHubAppSettings(
        app_id=os.environ.get("GITHUB_APP_ID"),
        slug=os.environ.get("GITHUB_APP_SLUG"),
        private_key=private_key,
        base_url=os.environ.get("GITHUB_BASE_URL", "https://github.com"),
        api_base_url=os.environ.get("GITHUB_API_BASE_URL", "https://api.github.com"),
    )


def build_app_jwt(settings: GitHubAppSettings) -> str:
    if not settings.configured:
        raise ValueError("GitHub App is not configured")
    private_key = settings.private_key
    if private_key is None:
        raise ValueError("GitHub App private key is missing")
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": settings.app_id,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token if isinstance(token, str) else token.decode()


async def get_repository_access(
    repo_slug: str,
    *,
    timeout_seconds: float = 15.0,
) -> GitHubAppRepositoryAccess:
    settings = load_github_app_settings()
    if not settings.configured:
        return GitHubAppRepositoryAccess(
            configured=False,
            repo_slug=repo_slug,
            accessible=False,
            reason="app_not_configured",
            install_url=settings.install_url,
        )

    jwt_token = build_app_jwt(settings)
    url = f"{settings.api_base_url.rstrip('/')}/repos/{repo_slug}/installation"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 200:
        return GitHubAppRepositoryAccess(
            configured=True,
            repo_slug=repo_slug,
            accessible=True,
            reason="authorized",
            install_url=settings.install_url,
        )
    if response.status_code in {403, 404}:
        return GitHubAppRepositoryAccess(
            configured=True,
            repo_slug=repo_slug,
            accessible=False,
            reason="repository_not_authorized",
            install_url=settings.install_url,
        )
    raise RuntimeError(f"GitHub App access check failed ({response.status_code}): {response.text}")


async def create_installation_token(
    repo_slug: str,
    *,
    timeout_seconds: float = 15.0,
) -> str:
    settings = load_github_app_settings()
    if not settings.configured:
        raise ValueError("GitHub App is not configured")
    jwt_token = build_app_jwt(settings)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        installation_response = await client.get(
            f"{settings.api_base_url.rstrip('/')}/repos/{repo_slug}/installation",
            headers=headers,
        )
        if installation_response.status_code >= 400:
            raise RuntimeError(
                f"GitHub App installation lookup failed ({installation_response.status_code}): "
                f"{installation_response.text}"
            )
        installation_id = installation_response.json()["id"]
        token_response = await client.post(
            f"{settings.api_base_url.rstrip('/')}/app/installations/{installation_id}/access_tokens",
            headers=headers,
        )
    if token_response.status_code >= 400:
        raise RuntimeError(
            f"GitHub App token creation failed ({token_response.status_code}): "
            f"{token_response.text}"
        )
    return token_response.json()["token"]
