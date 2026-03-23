from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from codeforge.domain.entities.repository import Repository

WORKSPACE_ROOT_ENV = "CODEFORGE_WORKSPACE_ROOT"
_VIRTUAL_PREFIX = "repo://"


def get_workspace_root() -> Path | None:
    value = __import__("os").environ.get(WORKSPACE_ROOT_ENV)
    if not value:
        return None
    path = Path(value).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_dir():
        return None
    return path


def build_virtual_repo_path(repo_slug: str) -> str:
    return f"{_VIRTUAL_PREFIX}{repo_slug}"


def is_virtual_repo_path(path: str) -> bool:
    return path.startswith(_VIRTUAL_PREFIX)


def derive_repo_slug(repo_url: str | None, fallback_name: str | None = None) -> str | None:
    if repo_url:
        candidate = repo_url.strip()
        if candidate.startswith("git@") and ":" in candidate:
            _, _, remainder = candidate.partition(":")
            candidate = remainder
        else:
            parsed = urlparse(candidate)
            if parsed.path:
                candidate = parsed.path.lstrip("/")
        if candidate.endswith(".git"):
            candidate = candidate[:-4]
        candidate = candidate.strip("/")
        if candidate:
            return candidate
    if fallback_name:
        return fallback_name.strip().replace(" ", "-")
    return None


def resolve_repository_local_path(repository: Repository) -> str | None:
    if repository.path:
        legacy_path = repository.path.strip()
        if legacy_path and not is_virtual_repo_path(legacy_path):
            resolved = _normalize_repo_path(Path(legacy_path))
            if resolved is not None:
                return resolved

    workspace_root = get_workspace_root()
    repo_slug = derive_repo_slug(repository.repo_url, repository.name)
    if workspace_root is None or repo_slug is None:
        return None

    repo_name = repo_slug.split("/")[-1]
    direct_candidates = [workspace_root / repo_slug, workspace_root / repo_name]
    for candidate in direct_candidates:
        resolved = _normalize_repo_path(candidate)
        if resolved is not None:
            return resolved

    for candidate in workspace_root.glob(f"*/{repo_name}"):
        resolved = _normalize_repo_path(candidate)
        if resolved is not None:
            return resolved

    for git_dir in workspace_root.rglob(".git"):
        candidate = git_dir.parent
        if candidate.name != repo_name:
            continue
        resolved = _normalize_repo_path(candidate)
        if resolved is not None:
            return resolved
    return None


def get_repository_location_status(repository: Repository) -> str:
    return "resolved" if resolve_repository_local_path(repository) else "missing"


def _normalize_repo_path(path: Path) -> str | None:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        return None
    if not (resolved / ".git").exists():
        return None
    return str(resolved)
