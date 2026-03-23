from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from codeforge.application.use_cases.push_task_to_github import push_task_to_github
from codeforge.application.use_cases.run_breakdown import BreakdownInput, run_breakdown
from codeforge.application.use_cases.run_code_review import (
    CodeReviewInput,
    CodeReviewReport,
    run_code_review,
)
from codeforge.application.use_cases.run_demand_assistant import (
    DemandAssistantInput,
    DemandAssistantResult,
    run_demand_assistant,
)
from codeforge.cli.config import (
    LocalConfig,
    find_project_root,
    init_local_config,
    load_local_config,
    save_local_config,
)
from codeforge.cli.output import render_diff_summary, render_projects, render_review, render_tasks
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import Repository
from codeforge.domain.entities.story import Story
from codeforge.domain.entities.task import AssigneeType, Task, TaskStatus
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId
from codeforge.infrastructure.ai.litellm_provider import LiteLLMProvider
from codeforge.infrastructure.config.workspace import resolve_repository_local_path
from codeforge.infrastructure.execution.claude_code_executor import (
    ClaudeCodeExecutor,
    ExecutionConfig,
    build_task_prompt,
)
from codeforge.infrastructure.git.git_service import GitService
from codeforge.infrastructure.integrations.github_gateway import GitHubGateway
from codeforge.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    init_database,
)
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyDemandRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRepositoryStore,
    SqlAlchemyStoryRepository,
    SqlAlchemyTaskExecutionRepository,
    SqlAlchemyTaskRepository,
    SqlAlchemyTaskReviewRepository,
)

app = typer.Typer(help="CodeForge CLI")
project_app = typer.Typer(help="Gerenciamento de projetos")
task_app = typer.Typer(help="Gerenciamento de tasks")
breakdown_app = typer.Typer(help="Breakdown automatico de stories")
demand_app = typer.Typer(help="Assistente de demandas")
config_app = typer.Typer(help="Configuracao local")
app.add_typer(project_app, name="project")
app.add_typer(task_app, name="task")
app.add_typer(breakdown_app, name="breakdown")
app.add_typer(demand_app, name="demand")
app.add_typer(config_app, name="config")
console = Console()


@dataclass
class _Runtime:
    project_root: Path
    config: LocalConfig
    engine: AsyncEngine
    session_factory: async_sessionmaker
    project_repo: SqlAlchemyProjectRepository
    repository_store: SqlAlchemyRepositoryStore
    demand_repo: SqlAlchemyDemandRepository
    story_repo: SqlAlchemyStoryRepository
    task_repo: SqlAlchemyTaskRepository
    task_execution_repo: SqlAlchemyTaskExecutionRepository
    task_review_repo: SqlAlchemyTaskReviewRepository


def _run_async[T](fn: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(fn)


async def _open_runtime(project_root: Path) -> _Runtime:
    config = load_local_config(project_root)
    engine = create_engine(config.database.url)
    session_factory = create_session_factory(engine)
    await init_database(engine)
    return _Runtime(
        project_root=project_root,
        config=config,
        engine=engine,
        session_factory=session_factory,
        project_repo=SqlAlchemyProjectRepository(session_factory),
        repository_store=SqlAlchemyRepositoryStore(session_factory),
        demand_repo=SqlAlchemyDemandRepository(session_factory),
        story_repo=SqlAlchemyStoryRepository(session_factory),
        task_repo=SqlAlchemyTaskRepository(session_factory),
        task_execution_repo=SqlAlchemyTaskExecutionRepository(session_factory),
        task_review_repo=SqlAlchemyTaskReviewRepository(session_factory),
    )


async def _close_runtime(runtime: _Runtime) -> None:
    await runtime.engine.dispose()


async def _get_current_project(runtime: _Runtime) -> Project:
    projects = await runtime.project_repo.list_all()
    for project in projects:
        repos = await runtime.repository_store.list_by_project(project.id)
        for repo in repos:
            local_path = resolve_repository_local_path(repo)
            if local_path and Path(local_path).resolve() == runtime.project_root.resolve():
                return project
    project = Project.create(name=runtime.config.project.name)
    await runtime.project_repo.save(project)
    repository = Repository.create(
        project_id=project.id,
        name=runtime.config.project.name,
        slug=runtime.config.project.name.lower().replace(" ", "-"),
        repo_url="",
        default_branch=runtime.config.project.default_branch,
        path=str(runtime.project_root),
    )
    await runtime.repository_store.save(repository)
    return project


async def _get_first_repository(runtime: _Runtime, project: Project) -> Repository | None:
    repos = await runtime.repository_store.list_by_project(project.id)
    return repos[0] if repos else None


@project_app.command("init")
def project_init(path: str) -> None:
    project_root = Path(path).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / ".codeforge" / "worktrees").mkdir(parents=True, exist_ok=True)
    config = init_local_config(project_root)
    save_local_config(project_root, config)

    async def _init() -> None:
        runtime = await _open_runtime(project_root)
        try:
            project = Project.create(name=config.project.name)
            await runtime.project_repo.save(project)
            repository = Repository.create(
                project_id=project.id,
                name=config.project.name,
                slug=config.project.name.lower().replace(" ", "-"),
                repo_url="",
                default_branch=config.project.default_branch,
                path=str(project_root),
            )
            await runtime.repository_store.save(repository)
        finally:
            await _close_runtime(runtime)

    _run_async(_init())
    console.print(Panel(f"Projeto inicializado em {project_root}", title="OK"))


@project_app.command("status")
def project_status() -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Nenhum projeto inicializado encontrado.")

    async def _status() -> list[Project]:
        runtime = await _open_runtime(project_root)
        try:
            return await runtime.project_repo.list_all()
        finally:
            await _close_runtime(runtime)

    projects = _run_async(_status())
    render_projects(console, projects)


@task_app.command("create")
def task_create(
    title: str,
    description: str = typer.Option("", "--description"),
    file: str | None = typer.Option(None, "--file"),
) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Execute 'codeforge project init <path>' primeiro.")

    async def _create() -> Task:
        runtime = await _open_runtime(project_root)
        try:
            task_description = description
            if file:
                task_description = Path(file).read_text(encoding="utf-8")
            if not task_description.strip():
                task_description = title
            project = await _get_current_project(runtime)
            task, _ = Task.create(project_id=project.id, title=title, description=task_description)
            await runtime.task_repo.save(task)
            return task
        finally:
            await _close_runtime(runtime)

    task = _run_async(_create())
    console.print(f"Task criada: [bold]{task.id}[/bold]")


@task_app.command("list")
def task_list(status: str | None = typer.Option(None, "--status")) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _list() -> list[Task]:
        runtime = await _open_runtime(project_root)
        try:
            project = await _get_current_project(runtime)
            task_status = TaskStatus(status) if status else None
            return await runtime.task_repo.list_by_project(project.id, task_status)
        finally:
            await _close_runtime(runtime)

    tasks = _run_async(_list())
    render_tasks(console, tasks)


@task_app.command("run")
def task_run(
    task_id: str,
    review: bool | None = typer.Option(None, "--review/--no-review"),
) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _run() -> tuple[Task, list[str], str]:
        runtime = await _open_runtime(project_root)
        try:
            project = await _get_current_project(runtime)
            repository = await _get_first_repository(runtime, project)
            task = await runtime.task_repo.get_by_id(TaskId(task_id))
            if task is None:
                raise ValueError(f"Task {task_id} nao encontrada")
            repo_path = resolve_repository_local_path(repository) if repository else None
            if repo_path is None:
                raise ValueError("Repositorio local nao encontrado para este projeto")
            git_service = GitService()
            worktree = await git_service.create_worktree(repo_path, str(task.id))
            task.worktree_path = worktree.path
            task.branch_name = worktree.branch
            task.assign_to(AssigneeType.AI)
            await runtime.task_repo.save(task)

            acceptance = _extract_acceptance_criteria(task.description)
            prompt = await build_task_prompt(
                task.title,
                task.description,
                acceptance,
                worktree.path,
            )
            executor = ClaudeCodeExecutor()
            result = await executor.execute(
                ExecutionConfig(
                    executor=runtime.config.agent.executor,
                    task_prompt=prompt,
                    worktree_path=worktree.path,
                    timeout_seconds=runtime.config.agent.execution_timeout,
                )
            )
            await runtime.task_execution_repo.save(
                task_id=task.id,
                success=result.success,
                exit_code=result.exit_code,
                output=result.output,
                changed_files=result.changed_files,
                diff=result.diff,
            )
            return task, result.changed_files, result.diff
        finally:
            await _close_runtime(runtime)

    task, changed_files, diff = _run_async(_run())
    console.print(Panel(f"Execucao concluida para task {task.id}", title="Task Run"))
    render_diff_summary(console, changed_files, diff)

    should_review = review
    if should_review is None and sys.stdin.isatty():
        should_review = typer.confirm("Rodar code review automatico agora?", default=True)
    if should_review:
        task_review(str(task.id))


@task_app.command("review")
def task_review(task_id: str) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _review() -> tuple[str, CodeReviewReport]:
        runtime = await _open_runtime(project_root)
        try:
            task = await runtime.task_repo.get_by_id(TaskId(task_id))
            if task is None:
                raise ValueError(f"Task {task_id} nao encontrada")
            execution = await runtime.task_execution_repo.get_by_task_id(task.id)
            if execution is None:
                raise ValueError("Task ainda nao possui execucao salva")

            report = await run_code_review(
                input=CodeReviewInput(
                    task_title=task.title,
                    task_description=task.description,
                    acceptance_criteria=_extract_acceptance_criteria(task.description),
                    diff=str(execution["diff"]),
                    changed_files=list(execution["changed_files"]),
                ),
                provider=LiteLLMProvider(),
                model=ModelId(runtime.config.agent.model),
            )
            await runtime.task_review_repo.save(
                task_id=task.id,
                verdict=report.verdict,
                summary=report.summary,
                issues=[
                    {
                        "title": issue.title,
                        "severity": issue.severity,
                        "description": issue.description,
                        "file_path": issue.file_path or "",
                    }
                    for issue in report.issues
                ],
            )
            return str(task.id), report
        finally:
            await _close_runtime(runtime)

    review_result = _run_async(_review())
    report: CodeReviewReport = review_result[1]
    render_review(console, report)


@task_app.command("push")
def task_push(task_id: str) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _push() -> str:
        runtime = await _open_runtime(project_root)
        try:
            task = await runtime.task_repo.get_by_id(TaskId(task_id))
            if task is None:
                raise ValueError(f"Task {task_id} nao encontrada")
            project = await runtime.project_repo.get_by_id(task.project_id)
            if project is None:
                raise ValueError(f"Projeto da task {task_id} nao encontrado")
            repository = await _get_first_repository(runtime, project)
            if repository is None:
                raise ValueError(f"Nenhum repositorio encontrado para o projeto {project.name}")
            result = await push_task_to_github(
                task=task,
                repository=repository,
                task_repo=runtime.task_repo,
                github_gateway=GitHubGateway(),
                git_service=GitService(),
                acceptance_criteria=_extract_acceptance_criteria(task.description),
            )
            return result.pr_url
        finally:
            await _close_runtime(runtime)

    pr_url = _run_async(_push())
    console.print(Panel(f"PR criado: {pr_url}", title="Task Push"))


@task_app.command("status")
def task_status(task_id: str) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _status() -> tuple[Task, dict | None, dict | None]:
        runtime = await _open_runtime(project_root)
        try:
            task = await runtime.task_repo.get_by_id(TaskId(task_id))
            if task is None:
                raise ValueError(f"Task {task_id} nao encontrada")
            execution = await runtime.task_execution_repo.get_by_task_id(task.id)
            review = await runtime.task_review_repo.get_by_task_id(task.id)
            return task, execution, review
        finally:
            await _close_runtime(runtime)

    task, execution, review = _run_async(_status())
    body = [
        f"status: {task.status.value}",
        f"branch: {task.branch_name or '-'}",
        f"worktree: {task.worktree_path or '-'}",
        f"pr: {task.pr_url or '-'}",
    ]
    if execution:
        body.append(f"changed_files: {len(execution['changed_files'])}")
        body.append(f"diff_chars: {len(execution['diff'])}")
    if review:
        body.append(f"review: {review['verdict']}")
    console.print(Panel("\n".join(body), title=f"Task {task.id}"))


@breakdown_app.command("run")
def breakdown_run(story_id: str, repo: str = typer.Option(..., "--repo")) -> None:
    repo_path = Path(repo).resolve()
    project_root = find_project_root(repo_path)
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado para o repositorio informado.")

    async def _breakdown() -> tuple[Story, int, bool]:
        runtime = await _open_runtime(project_root)
        try:
            story = await runtime.story_repo.get_by_id(StoryId(story_id))
            if story is None:
                raise ValueError(f"Story {story_id} nao encontrada")
            project = await _get_current_project(runtime)

            result = await run_breakdown(
                input=BreakdownInput(
                    story_id=story.id,
                    story_title=story.title,
                    story_description=story.description,
                    repo_path=str(repo_path),
                    project_id=project.id,
                ),
                provider=LiteLLMProvider(),
                model=ModelId(runtime.config.agent.model),
                task_repo=runtime.task_repo,
            )
            return story, len(result.tasks), result.success
        finally:
            await _close_runtime(runtime)

    story, created, success = _run_async(_breakdown())
    title = "Breakdown concluido" if success else "Breakdown incompleto"
    console.print(
        Panel(
            f"Story: {story.title}\nTasks criadas: {created}",
            title=title,
        )
    )


@demand_app.command("create")
def demand_create(description: str) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")

    async def _generate() -> tuple[Project, DemandAssistantResult]:
        runtime = await _open_runtime(project_root)
        try:
            project = await _get_current_project(runtime)
            result = await run_demand_assistant(
                input=DemandAssistantInput(
                    description=description,
                    project_id=project.id,
                ),
                provider=LiteLLMProvider(),
                model=ModelId(runtime.config.agent.model),
                demand_repo=runtime.demand_repo,
                story_repo=runtime.story_repo,
                persist=False,
            )
            return project, result
        finally:
            await _close_runtime(runtime)

    _project, result = _run_async(_generate())
    objective = result.demand.business_objective
    stories_block = "\n".join(f"- {story.title}" for story in result.stories) or "- Nenhuma"
    console.print(
        Panel(
            f"Objetivo:\n{objective}\n\nStories propostas:\n{stories_block}",
            title="Demand Assistant",
        )
    )
    if not typer.confirm("Salvar?", default=False):
        return

    async def _save() -> None:
        runtime = await _open_runtime(project_root)
        try:
            await runtime.demand_repo.save(result.demand)
            for story in result.stories:
                await runtime.story_repo.save(story)
            console.print(
                Panel(
                    f"Demanda salva: {result.demand.id}\nStories: {len(result.stories)}",
                    title="Salvo",
                )
            )
        finally:
            await _close_runtime(runtime)

    _run_async(_save())


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    project_root = find_project_root()
    if project_root is None:
        raise typer.BadParameter("Projeto nao inicializado.")
    config = load_local_config(project_root)
    if key == "model":
        config.agent.model = value
    elif key == "executor":
        config.agent.executor = value
    elif key == "execution_timeout":
        config.agent.execution_timeout = int(value)
    elif key == "default_branch":
        config.project.default_branch = value
    else:
        raise typer.BadParameter(f"Chave nao suportada: {key}")
    save_local_config(project_root, config)
    console.print(Panel(f"{key} atualizado para {value}", title="Config"))


def _extract_acceptance_criteria(description: str) -> list[str]:
    criteria = [
        line.strip("- ").strip()
        for line in description.splitlines()
        if line.strip().startswith("-")
    ]
    if not criteria:
        return ["Implement task exactly as requested", "Run relevant tests"]
    return criteria


if __name__ == "__main__":
    app()
