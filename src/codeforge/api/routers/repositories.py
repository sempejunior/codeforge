from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.repository import RepositoryCreateSchema, RepositoryResponseSchema
from codeforge.application.use_cases.run_repository_analysis import (
    AnalysisInput,
    run_repository_analysis,
)
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.entities.team_document import TeamDocument, TeamDocumentSource
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.infrastructure.config.workspace import (
    build_virtual_repo_path,
    derive_repo_slug,
    get_repository_location_status,
    resolve_repository_local_path,
)
from codeforge.infrastructure.integrations.github_app import load_github_app_settings

router = APIRouter(prefix="/api/projects/{project_id}/repositories", tags=["repositories"])

SKILLS_DIR = Path(__file__).parents[2] / "skills"


@router.get("", response_model=list[RepositoryResponseSchema])
async def list_repositories(
    project_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[RepositoryResponseSchema]:
    project = await repositories.project_repository.get_by_id(ProjectId(project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    items = await repositories.repository_store.list_by_project(project.id)
    return [_to_response(item) for item in items]


@router.post("", response_model=RepositoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_repository(
    project_id: str,
    payload: RepositoryCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> RepositoryResponseSchema:
    project = await repositories.project_repository.get_by_id(ProjectId(project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    normalized_repo_url, warnings = _validate_repo_url(payload.repo_url)
    assert normalized_repo_url is not None

    existing = await repositories.repository_store.get_by_repo_url(normalized_repo_url)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already registered",
        )

    repo_slug = payload.slug or derive_repo_slug(normalized_repo_url, payload.name)
    if repo_slug is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not derive repository slug",
        )

    repository = Repository.create(
        project_id=project.id,
        name=payload.name,
        slug=repo_slug,
        repo_url=normalized_repo_url,
        default_branch=payload.default_branch,
        path=build_virtual_repo_path(repo_slug),
    )
    await repositories.repository_store.save(repository)

    if project.team_id is not None:
        project_folder = await repositories.team_document_repository.find_folder_for_project(
            project.team_id, project.id
        )
        existing_repo_folder = await repositories.team_document_repository.find_folder_for_repository(
            project.team_id, repository.id
        )
        if existing_repo_folder is None:
            repo_folder = TeamDocument.create_folder(
                team_id=project.team_id,
                title=repository.name,
                parent_id=project_folder.id if project_folder else None,
                source=TeamDocumentSource.SYSTEM,
                linked_repository_id=repository.id,
            )
            await repositories.team_document_repository.save(repo_folder)

    return _to_response(repository, warnings=warnings)


@router.get("/{repository_id}", response_model=RepositoryResponseSchema)
async def get_repository(
    project_id: str,
    repository_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> RepositoryResponseSchema:
    repository = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
    if repository is None or str(repository.project_id) != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return _to_response(repository)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    project_id: str,
    repository_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    repository = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
    if repository is None or str(repository.project_id) != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    repo_docs = await repositories.team_document_repository.list_by_repository(repository.id)
    for doc in reversed(repo_docs):
        await repositories.team_document_repository.delete(doc.id)

    await repositories.repository_store.delete(repository.id)


@router.post("/{repository_id}/analyze")
async def trigger_analysis(
    project_id: str,
    repository_id: str,
    request: Request,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> dict[str, str]:
    repository = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
    if repository is None or str(repository.project_id) != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    jobs: dict[str, asyncio.Task] = request.app.state.analysis_jobs
    existing = jobs.get(repository_id)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis already in progress",
        )

    async def _run() -> None:
        await run_repository_analysis(
            AnalysisInput(repository_id=RepositoryId(repository_id)),
            repositories.repository_store,
            SKILLS_DIR,
            repositories.team_document_repository,
            repositories.project_repository,
        )

    task = asyncio.create_task(_run())
    jobs[repository_id] = task
    task.add_done_callback(lambda _: jobs.pop(repository_id, None))

    return {"status": "analyzing"}


@router.get("/{repository_id}/analysis-status")
async def get_analysis_status(
    project_id: str,
    repository_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> dict[str, str | None]:
    repository = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
    if repository is None or str(repository.project_id) != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    return {
        "analysis_status": repository.analysis_status.value,
        "context_doc": (
            repository.context_doc
            if repository.analysis_status == AnalysisStatus.DONE
            else None
        ),
        "analysis_error": repository.analysis_error,
    }


@router.get("/{repository_id}/analysis-stream")
async def analysis_stream(
    project_id: str,
    repository_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StreamingResponse:
    repository = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
    if repository is None or str(repository.project_id) != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    async def _stream():
        for _ in range(600):
            await asyncio.sleep(1)
            repo = await repositories.repository_store.get_by_id(RepositoryId(repository_id))
            if repo is None:
                break

            s = repo.analysis_status.value
            if s == "done":
                yield f"data: {json.dumps({'status': 'done', 'context_doc': repo.context_doc})}\n\n"
                break
            elif s == "error":
                payload = {
                    "status": "error",
                    "message": repo.analysis_error or "Analysis failed",
                }
                yield f"data: {json.dumps(payload)}\n\n"
                break
            else:
                yield f"data: {json.dumps({'status': s})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


def _to_response(
    repository: Repository,
    warnings: list[str] | None = None,
) -> RepositoryResponseSchema:
    resolved_local_path = resolve_repository_local_path(repository)
    response_warnings = _build_repository_warnings(repository)
    if warnings:
        for warning in warnings:
            if warning not in response_warnings:
                response_warnings.append(warning)
    return RepositoryResponseSchema(
        id=str(repository.id),
        project_id=str(repository.project_id),
        name=repository.name,
        slug=repository.slug,
        repo_url=repository.repo_url,
        default_branch=repository.default_branch,
        path=resolved_local_path,
        status=repository.status.value,
        context_doc=repository.context_doc,
        analysis_status=repository.analysis_status.value,
        analysis_executor=repository.analysis_executor,
        analysis_error=repository.analysis_error,
        local_path_hint=repository.local_path_hint,
        local_path_status=get_repository_location_status(repository),
        warnings=response_warnings,
        created_at=repository.created_at,
        updated_at=repository.updated_at,
    )


def _build_repository_warnings(repository: Repository) -> list[str]:
    warnings: list[str] = []
    github_app = load_github_app_settings()
    if repository.repo_url and _is_github_repo_url(repository.repo_url) and not github_app.configured:
        warnings.append(
            "Repositorio GitHub pode exigir autorizacao. "
            "Conecte o GitHub App nas configuracoes gerais."
        )
    if resolve_repository_local_path(repository) is None:
        warnings.append(
            "Workspace local ainda nao configurado para execucao de codigo."
        )
    return warnings


def _validate_repo_url(repo_url: str | None) -> tuple[str | None, list[str]]:
    if repo_url is None:
        return None, []
    normalized_repo_url = repo_url.strip()
    if not normalized_repo_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="URL do repositorio nao pode ser vazia",
        )
    if not _is_valid_git_url(normalized_repo_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="URL do repositorio invalida",
        )
    warnings: list[str] = []
    github_app = load_github_app_settings()
    if _is_github_repo_url(normalized_repo_url) and not github_app.configured:
        warnings.append(
            "Repositorio privado pode exigir autorizacao via GitHub App. "
            "Conecte e libere acesso ao repositorio."
        )
    return normalized_repo_url, warnings


def _is_valid_git_url(repo_url: str) -> bool:
    parsed = urlparse(repo_url)
    if parsed.scheme in {"http", "https", "ssh"}:
        return bool(parsed.netloc and parsed.path and parsed.path != "/")
    return bool(re.fullmatch(r"git@[^\s:]+:[^\s]+", repo_url))


def _is_github_repo_url(repo_url: str) -> bool:
    parsed = urlparse(repo_url)
    if parsed.netloc:
        return parsed.netloc.lower() == "github.com"
    return repo_url.startswith("git@github.com:")
