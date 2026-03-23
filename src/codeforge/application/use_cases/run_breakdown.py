from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome
from codeforge.domain.entities.task import Task
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.infrastructure.tools.base import ToolContext
from codeforge.infrastructure.tools.glob_tool import GlobTool
from codeforge.infrastructure.tools.grep_tool import GrepTool
from codeforge.infrastructure.tools.read_tool import ReadTool


@dataclass
class BreakdownInput:
    story_id: StoryId
    story_title: str
    story_description: str
    repo_path: str
    project_id: ProjectId
    context_doc: str | None = None
    workspace_context: str | None = None


@dataclass
class BreakdownResult:
    tasks: list[Task]
    raw_output: str
    success: bool


class _BreakdownTaskSchema(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    depends_on_titles: list[str] = Field(default_factory=list)


class _BreakdownOutputSchema(BaseModel):
    tasks: list[_BreakdownTaskSchema] = Field(default_factory=list)


async def run_breakdown(
    input: BreakdownInput,
    provider: AIProviderPort,
    model: ModelId,
    task_repo: TaskRepositoryPort,
) -> BreakdownResult:
    repo_path = Path(input.repo_path).resolve()
    tool_context = ToolContext(cwd=repo_path, project_dir=repo_path)
    tools = {
        "Read": ReadTool().bind(tool_context),
        "Glob": GlobTool().bind(tool_context),
        "Grep": GrepTool().bind(tool_context),
    }

    prompt = (
        "Break down this story into implementation tasks for an AI coding agent. "
        "Read the repository first using tools and ground every task in real files "
        "and patterns.\n\n"
        f"Story title: {input.story_title}\n\n"
        f"Story description:\n{input.story_description}\n\n"
        "Return JSON only."
    )

    extra_context_parts = [
        part
        for part in (input.context_doc, input.workspace_context)
        if part
    ]
    extra_context = "\n\n---\n\n".join(extra_context_parts) if extra_context_parts else None

    result = await run_agent_session(
        config=SessionConfig(
            agent_type=AgentType.BREAKDOWN,
            model=model,
            system_prompt=build_system_prompt(
                AgentType.BREAKDOWN,
                project_path=repo_path,
                extra_context=extra_context,
            ),
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            max_steps=50,
            output_schema=_BreakdownOutputSchema,
        ),
        provider=provider,
    )

    raw_output = _extract_raw_output(result.messages)
    if result.outcome != SessionOutcome.COMPLETED or result.structured_output is None:
        return BreakdownResult(tasks=[], raw_output=raw_output, success=False)

    created_tasks: list[Task] = []
    parsed = result.structured_output
    if not isinstance(parsed, _BreakdownOutputSchema):
        return BreakdownResult(tasks=[], raw_output=raw_output, success=False)
    for item in parsed.tasks:
        details = [item.description.strip()]
        if item.acceptance_criteria:
            details.append(
                "Acceptance criteria:\n"
                + "\n".join(f"- {criterion}" for criterion in item.acceptance_criteria)
            )
        if item.depends_on_titles:
            details.append(
                "Dependencies:\n" + "\n".join(f"- {dep}" for dep in item.depends_on_titles)
            )
        task, _ = Task.create(
            project_id=input.project_id,
            title=item.title,
            description="\n\n".join(details),
            story_id=input.story_id,
        )
        await task_repo.save(task)
        created_tasks.append(task)

    return BreakdownResult(tasks=created_tasks, raw_output=raw_output, success=True)


def _extract_raw_output(messages: list[dict]) -> str:
    assistant_messages = [m.get("content", "") for m in messages if m.get("role") == "assistant"]
    return "\n\n".join(str(content) for content in assistant_messages if content)
