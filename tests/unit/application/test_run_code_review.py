from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from codeforge.application.use_cases.run_code_review import CodeReviewInput, run_code_review
from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.ports.ai_provider import AIProviderPort, GenerateResult, StreamPart
from codeforge.domain.value_objects.model_id import ModelId


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


@pytest.mark.asyncio
async def test_run_code_review_returns_structured_report() -> None:
    provider = _MockProvider(
        """
        ```json
        {
          "verdict": "approved",
          "issues": [],
          "summary": "Tudo certo"
        }
        ```
        """
    )

    report = await run_code_review(
        input=CodeReviewInput(
            task_title="Task",
            task_description="Desc",
            acceptance_criteria=["Criterion"],
            diff="diff --git",
            changed_files=["src/a.py"],
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
    )

    assert report.verdict == "approved"
    assert report.summary == "Tudo certo"
    assert report.issues == []


@pytest.mark.asyncio
async def test_run_code_review_returns_fallback_when_unstructured() -> None:
    provider = _MockProvider("texto sem json")

    report = await run_code_review(
        input=CodeReviewInput(
            task_title="Task",
            task_description="Desc",
            acceptance_criteria=[],
            diff="",
            changed_files=[],
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
    )

    assert report.verdict == "changes_requested"
    assert len(report.issues) == 1
    assert report.issues[0].title == "Code review inconclusive"
