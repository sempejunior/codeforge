from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from codeforge.application.use_cases.run_breakdown import BreakdownInput, run_breakdown
from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.entities.task import Task
from codeforge.domain.ports.ai_provider import AIProviderPort, GenerateResult, StreamPart
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId


class _MockProvider(AIProviderPort):
    def __init__(self, content: str) -> None:
        self._content = content

    async def generate_stream(
        self,
        model,
        system,
        messages,
        tools=None,
        thinking=None,
        abort_event=None,
    ) -> AsyncGenerator[StreamPart, None]:
        del model, system, messages, tools, thinking, abort_event

        async def _gen() -> AsyncGenerator[StreamPart, None]:
            yield StreamPart(type="text_delta", content=self._content)
            yield StreamPart(type="finish", finish_reason="stop")

        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        del model, system, messages
        return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")


class _TaskRepo(TaskRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Task] = []

    async def save(self, task: Task) -> None:
        self.saved.append(task)

    async def get_by_id(self, task_id: TaskId) -> Task | None:
        del task_id
        return None

    async def list_by_project(self, project_id: ProjectId, status=None) -> list[Task]:
        del project_id, status
        return []

    async def delete(self, task_id: TaskId) -> None:
        del task_id


@pytest.mark.asyncio
async def test_run_breakdown_creates_tasks_from_structured_output() -> None:
    provider = _MockProvider(
        """
        {
          "tasks": [
            {
              "title": "Add auth endpoint",
              "description": "Update src/api/auth.py",
              "acceptance_criteria": ["Endpoint returns 200"],
              "depends_on_titles": []
            }
          ]
        }
        """
    )
    repo = _TaskRepo()

    result = await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Login flow",
            story_description="Implement login",
            repo_path=".",
            project_id=ProjectId.generate(),
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=repo,
    )

    assert result.success is True
    assert len(result.tasks) == 1
    assert repo.saved[0].title == "Add auth endpoint"
    assert "Acceptance criteria" in repo.saved[0].description


@pytest.mark.asyncio
async def test_run_breakdown_injects_context_doc_into_system_prompt() -> None:
    captured_system: list[str] = []

    class _CapturingProvider(AIProviderPort):
        async def generate_stream(
            self, model, system, messages,
            tools=None, thinking=None, abort_event=None,
        ):
            captured_system.append(system)

            async def _gen():
                yield StreamPart(
                    type="text_delta",
                    content='{"tasks": [{"title": "T1", "description": "D1"}]}',
                )
                yield StreamPart(type="finish", finish_reason="stop")
            return _gen()

        async def generate(self, model, system, messages) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    repo = _TaskRepo()
    context = "## Architecture\nFastAPI + SQLAlchemy + React"

    await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Story",
            story_description="Desc",
            repo_path=".",
            project_id=ProjectId.generate(),
            context_doc=context,
        ),
        provider=_CapturingProvider(),
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=repo,
    )

    assert len(captured_system) > 0
    assert "FastAPI + SQLAlchemy + React" in captured_system[0]
    assert "Additional Context" in captured_system[0]


@pytest.mark.asyncio
async def test_run_breakdown_works_without_context_doc() -> None:
    captured_system: list[str] = []

    class _CapturingProvider(AIProviderPort):
        async def generate_stream(
            self, model, system, messages,
            tools=None, thinking=None, abort_event=None,
        ):
            captured_system.append(system)

            async def _gen():
                yield StreamPart(
                    type="text_delta",
                    content='{"tasks": [{"title": "T1", "description": "D1"}]}',
                )
                yield StreamPart(type="finish", finish_reason="stop")
            return _gen()

        async def generate(self, model, system, messages) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    repo = _TaskRepo()

    await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Story",
            story_description="Desc",
            repo_path=".",
            project_id=ProjectId.generate(),
        ),
        provider=_CapturingProvider(),
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=repo,
    )

    assert len(captured_system) > 0
    assert "Additional Context" not in captured_system[0]


@pytest.mark.asyncio
async def test_run_breakdown_returns_failure_when_unstructured_output() -> None:
    provider = _MockProvider("not json")
    repo = _TaskRepo()

    result = await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Story",
            story_description="Desc",
            repo_path=".",
            project_id=ProjectId.generate(),
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=repo,
    )

    assert result.success is False
    assert result.tasks == []
    assert repo.saved == []
