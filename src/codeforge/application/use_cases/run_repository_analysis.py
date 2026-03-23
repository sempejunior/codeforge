from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from loguru import logger

from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.entities.team_document import TeamDocument, TeamDocumentKind, TeamDocumentSource
from codeforge.domain.ports.github_gateway import GitHubGatewayPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.team_document_repository import TeamDocumentRepositoryPort
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.infrastructure.config.workspace import derive_repo_slug, resolve_repository_local_path
from codeforge.infrastructure.integrations.github_gateway import GitHubGateway
from codeforge.infrastructure.skills.loader import SkillsLoader


@dataclass
class AnalysisInput:
    repository_id: RepositoryId
    timeout_seconds: int = 300


@dataclass
class AnalysisResult:
    success: bool
    context_doc: str
    executor_used: str
    error: str | None = None


async def run_repository_analysis(
    input: AnalysisInput,
    repository_store: RepositoryStorePort,
    skills_dir: Path,
    team_document_repo: TeamDocumentRepositoryPort | None = None,
    project_repository: ProjectRepositoryPort | None = None,
    github_gateway: GitHubGatewayPort | None = None,
) -> AnalysisResult:
    repository = await repository_store.get_by_id(input.repository_id)
    if repository is None:
        raise ValueError(f"Repository {input.repository_id} not found")

    loader = SkillsLoader(skills_dir)
    skill_name = loader.find_first_available("analyze-codebase")
    if skill_name is None:
        repository.analysis_executor = None
        return AnalysisResult(
            success=False,
            context_doc="",
            executor_used="",
            error="No analysis executor available. Install claude, opencode, or gemini CLI.",
        )

    meta = loader.get_metadata(skill_name)
    command_template: list[str] = meta.get("command", [])
    body = loader.load(skill_name) or ""

    prompt = _extract_prompt(body)
    command = [part.replace("{prompt}", prompt) for part in command_template]

    repository.analysis_status = AnalysisStatus.ANALYZING
    repository.analysis_executor = skill_name
    repository.analysis_error = None
    repository.updated_at = datetime.now(UTC)
    await repository_store.save(repository)

    logger.info("Starting analysis for repository {} with {}", repository.name, skill_name)

    try:
        repo_path, cleanup_dir = await _resolve_analysis_repo_path(
            repository=repository,
            github_gateway=github_gateway or GitHubGateway(),
        )
    except Exception as exc:
        repository.analysis_status = AnalysisStatus.ERROR
        repository.analysis_executor = skill_name
        repository.analysis_error = str(exc)
        repository.updated_at = datetime.now(UTC)
        await repository_store.save(repository)
        return AnalysisResult(
            success=False,
            context_doc="",
            executor_used=skill_name,
            error=str(exc),
        )

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=input.timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            repository.analysis_status = AnalysisStatus.ERROR
            repository.analysis_executor = skill_name
            repository.analysis_error = f"Analysis timed out after {input.timeout_seconds}s"
            repository.updated_at = datetime.now(UTC)
            await repository_store.save(repository)
            return AnalysisResult(
                success=False,
                context_doc="",
                executor_used=skill_name,
                error=f"Analysis timed out after {input.timeout_seconds}s",
            )

        output = stdout.decode("utf-8", errors="replace")
        exit_code = process.returncode or 0

        if exit_code != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            repository.analysis_status = AnalysisStatus.ERROR
            repository.analysis_executor = skill_name
            repository.analysis_error = f"Executor exited with code {exit_code}: {error_output[:500]}"
            repository.updated_at = datetime.now(UTC)
            await repository_store.save(repository)
            return AnalysisResult(
                success=False,
                context_doc="",
                executor_used=skill_name,
                error=f"Executor exited with code {exit_code}: {error_output[:500]}",
            )

        repository.context_doc = output
        repository.analysis_status = AnalysisStatus.DONE
        repository.analysis_executor = skill_name
        repository.analysis_error = None
        repository.updated_at = datetime.now(UTC)
        await repository_store.save(repository)

        await _save_context_team_document(
            repository=repository,
            context_doc=output,
            team_document_repo=team_document_repo,
            project_repository=project_repository,
        )

        return AnalysisResult(
            success=True,
            context_doc=output,
            executor_used=skill_name,
        )

    except Exception as exc:
        repository.analysis_status = AnalysisStatus.ERROR
        repository.analysis_executor = skill_name
        repository.analysis_error = str(exc)
        repository.updated_at = datetime.now(UTC)
        await repository_store.save(repository)
        return AnalysisResult(
            success=False,
            context_doc="",
            executor_used=skill_name,
            error=str(exc),
        )
    finally:
        if cleanup_dir is not None:
            cleanup_dir.cleanup()


def _extract_prompt(body: str) -> str:
    lines = body.strip().splitlines()
    prompt_lines: list[str] = []
    in_prompt = False

    for line in lines:
        if line.strip().startswith("## Prompt"):
            in_prompt = True
            continue
        if in_prompt and line.strip().startswith("## "):
            break
        if in_prompt:
            prompt_lines.append(line)

    if prompt_lines:
        return "\n".join(prompt_lines).strip()

    return (
        "Analyze this codebase and produce a structured context document. "
        "Output ONLY the document, no conversation."
    )


async def _resolve_analysis_repo_path(
    repository: Repository,
    github_gateway: GitHubGatewayPort,
) -> tuple[str, TemporaryDirectory[str] | None]:
    local_path = resolve_repository_local_path(repository)
    if local_path is not None:
        return local_path, None

    repo_slug = derive_repo_slug(repository.repo_url, repository.name)
    if repo_slug is not None and repository.repo_url and "github.com" in repository.repo_url:
        temp_dir = TemporaryDirectory(prefix="codeforge-analysis-")
        try:
            extracted_path = await github_gateway.download_repository_archive(
                repo=repo_slug,
                ref=repository.default_branch,
                destination_dir=Path(temp_dir.name),
            )
        except Exception:
            temp_dir.cleanup()
            raise RuntimeError(
                "CodeForge nao conseguiu acessar o repositorio no GitHub. "
                "Conecte o GitHub App e libere acesso a este repositorio nas configuracoes."
            ) from None
        return str(extracted_path), temp_dir

    raise RuntimeError(
        "Repositorio indisponivel para analise. Configure repo_url no GitHub "
        "ou mantenha uma copia local acessivel."
    )


async def _save_context_team_document(
    repository: Repository,
    context_doc: str,
    team_document_repo: TeamDocumentRepositoryPort | None,
    project_repository: ProjectRepositoryPort | None,
) -> None:
    if team_document_repo is None or project_repository is None:
        return

    project = await project_repository.get_by_id(repository.project_id)
    if project is None or project.team_id is None:
        return

    team_id = project.team_id

    repo_folder = await team_document_repo.find_folder_for_repository(
        team_id, repository.id
    )
    parent_id = repo_folder.id if repo_folder else None

    existing = await team_document_repo.find_generated_repo_context_document(
        team_id, repository.id
    )
    if existing is not None:
        existing.content = context_doc
        existing.updated_at = datetime.now(UTC)
        await team_document_repo.save(existing)
    else:
        doc = TeamDocument.create_document(
            team_id=team_id,
            title="Contexto Gerado",
            content=context_doc,
            parent_id=parent_id,
            source=TeamDocumentSource.GENERATED,
            linked_repository_id=repository.id,
        )
        await team_document_repo.save(doc)
