from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from codeforge.infrastructure.config.workspace import WORKSPACE_ROOT_ENV
from codeforge.infrastructure.integrations.github_app import (
    get_repository_access,
    load_github_app_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_ENV_FILE = Path(__file__).parents[4] / ".env"

_ALLOWED_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
}


class ApiKeysPayload(BaseModel):
    keys: dict[str, str]


class ApiKeysStatus(BaseModel):
    keys: dict[str, bool]


class WorkspaceSettingsPayload(BaseModel):
    workspace_root: str | None


class WorkspaceSettingsResponse(BaseModel):
    workspace_root: str | None


class GitHubAppStatusResponse(BaseModel):
    configured: bool
    app_slug: str | None
    install_url: str | None


class GitHubAppSavePayload(BaseModel):
    app_id: str
    app_slug: str
    private_key: str


class GitHubAppRepositoryAccessResponse(BaseModel):
    configured: bool
    repo_slug: str | None
    accessible: bool
    reason: str
    install_url: str | None


@router.get("/keys", response_model=ApiKeysStatus)
async def get_keys_status() -> ApiKeysStatus:
    return ApiKeysStatus(
        keys={key: bool(os.environ.get(key)) for key in _ALLOWED_KEYS}
    )


@router.put("/keys", response_model=ApiKeysStatus)
async def save_keys(payload: ApiKeysPayload) -> ApiKeysStatus:
    unknown = set(payload.keys) - _ALLOWED_KEYS
    if unknown:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Unknown keys: {unknown}")

    existing: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip()

    for key, value in payload.keys.items():
        if value:
            existing[key] = value
            os.environ[key] = value
        else:
            existing.pop(key, None)
            os.environ.pop(key, None)

    lines = [f"{k}={v}" for k, v in existing.items()]
    _ENV_FILE.write_text("\n".join(lines) + "\n")

    return ApiKeysStatus(
        keys={key: bool(os.environ.get(key)) for key in _ALLOWED_KEYS}
    )


@router.get("/workspace", response_model=WorkspaceSettingsResponse)
async def get_workspace_settings() -> WorkspaceSettingsResponse:
    return WorkspaceSettingsResponse(workspace_root=os.environ.get(WORKSPACE_ROOT_ENV))


@router.put("/workspace", response_model=WorkspaceSettingsResponse)
async def save_workspace_settings(
    payload: WorkspaceSettingsPayload,
) -> WorkspaceSettingsResponse:
    workspace_root = payload.workspace_root.strip() if payload.workspace_root else None
    if workspace_root:
        resolved = Path(workspace_root).expanduser().resolve(strict=False)
        if not resolved.exists() or not resolved.is_dir():
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail="Workspace root nao encontrado",
            )
        workspace_root = str(resolved)

    existing: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip()

    if workspace_root:
        existing[WORKSPACE_ROOT_ENV] = workspace_root
        os.environ[WORKSPACE_ROOT_ENV] = workspace_root
    else:
        existing.pop(WORKSPACE_ROOT_ENV, None)
        os.environ.pop(WORKSPACE_ROOT_ENV, None)

    lines = [f"{k}={v}" for k, v in existing.items()]
    _ENV_FILE.write_text("\n".join(lines) + "\n")
    return WorkspaceSettingsResponse(workspace_root=workspace_root)


@router.get("/github-app", response_model=GitHubAppStatusResponse)
async def get_github_app_status() -> GitHubAppStatusResponse:
    settings = load_github_app_settings()
    return GitHubAppStatusResponse(
        configured=settings.configured,
        app_slug=settings.slug,
        install_url=settings.install_url,
    )


@router.put("/github-app", response_model=GitHubAppStatusResponse)
async def save_github_app(payload: GitHubAppSavePayload) -> GitHubAppStatusResponse:
    existing: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip()

    app_id = payload.app_id.strip()
    app_slug = payload.app_slug.strip()
    private_key = payload.private_key.strip()

    if not app_id or not app_slug or not private_key:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="All fields (app_id, app_slug, private_key) are required",
        )

    serialized_key = private_key.replace("\n", "\\n")

    existing["GITHUB_APP_ID"] = app_id
    existing["GITHUB_APP_SLUG"] = app_slug
    existing["GITHUB_APP_PRIVATE_KEY"] = serialized_key

    os.environ["GITHUB_APP_ID"] = app_id
    os.environ["GITHUB_APP_SLUG"] = app_slug
    os.environ["GITHUB_APP_PRIVATE_KEY"] = serialized_key

    lines = [f"{k}={v}" for k, v in existing.items()]
    _ENV_FILE.write_text("\n".join(lines) + "\n")

    settings = load_github_app_settings()
    return GitHubAppStatusResponse(
        configured=settings.configured,
        app_slug=settings.slug,
        install_url=settings.install_url,
    )


@router.delete("/github-app", response_model=GitHubAppStatusResponse)
async def delete_github_app() -> GitHubAppStatusResponse:
    existing: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip()

    for key in ("GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_APP_PRIVATE_KEY"):
        existing.pop(key, None)
        os.environ.pop(key, None)

    lines = [f"{k}={v}" for k, v in existing.items()]
    _ENV_FILE.write_text("\n".join(lines) + "\n")

    settings = load_github_app_settings()
    return GitHubAppStatusResponse(
        configured=settings.configured,
        app_slug=settings.slug,
        install_url=settings.install_url,
    )


@router.get("/github-app/repository-access", response_model=GitHubAppRepositoryAccessResponse)
async def get_github_app_repository_access(repo_url: str) -> GitHubAppRepositoryAccessResponse:
    repo_slug = _derive_repo_slug(repo_url)
    access = await get_repository_access(repo_slug)
    return GitHubAppRepositoryAccessResponse(
        configured=access.configured,
        repo_slug=access.repo_slug,
        accessible=access.accessible,
        reason=access.reason,
        install_url=access.install_url,
    )


def _derive_repo_slug(repo_url: str) -> str:
    value = repo_url.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if ":" in value and value.startswith("git@"):
        value = value.split(":", 1)[1]
    if "/" in value:
        parts = value.split("/")
        return "/".join(parts[-2:])
    return value
