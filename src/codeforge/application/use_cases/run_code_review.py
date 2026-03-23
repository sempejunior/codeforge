from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import ToolContext
from codeforge.infrastructure.tools.glob_tool import GlobTool
from codeforge.infrastructure.tools.grep_tool import GrepTool
from codeforge.infrastructure.tools.read_tool import ReadTool


@dataclass
class CodeReviewIssue:
    title: str
    severity: Literal["critical", "major", "minor"]
    description: str
    file_path: str | None = None


@dataclass
class CodeReviewInput:
    task_title: str
    task_description: str
    acceptance_criteria: list[str]
    diff: str
    changed_files: list[str]


@dataclass
class CodeReviewReport:
    verdict: Literal["approved", "changes_requested"]
    issues: list[CodeReviewIssue]
    summary: str


class _IssueSchema(BaseModel):
    title: str
    severity: Literal["critical", "major", "minor"]
    description: str
    file_path: str | None = None


class _ReviewSchema(BaseModel):
    verdict: Literal["approved", "changes_requested"] = Field(default="changes_requested")
    issues: list[_IssueSchema] = Field(default_factory=list)
    summary: str = Field(default="Review completed")


async def run_code_review(
    input: CodeReviewInput,
    provider: AIProviderPort,
    model: ModelId,
) -> CodeReviewReport:
    project_path = Path.cwd()
    tool_context = ToolContext(cwd=project_path, project_dir=project_path)
    tools = {
        "Read": ReadTool().bind(tool_context),
        "Glob": GlobTool().bind(tool_context),
        "Grep": GrepTool().bind(tool_context),
    }

    criteria = "\n".join(f"- {criterion}" for criterion in input.acceptance_criteria)
    changed = "\n".join(f"- {file_path}" for file_path in input.changed_files)

    prompt = (
        "Review this code change and return JSON only.\n\n"
        f"Task title: {input.task_title}\n\n"
        f"Task description:\n{input.task_description}\n\n"
        f"Acceptance criteria:\n{criteria or '- None provided'}\n\n"
        f"Changed files:\n{changed or '- No changed files'}\n\n"
        "Git diff:\n"
        f"{input.diff[:50_000]}\n\n"
        "Rules:\n"
        "- Verify scope, correctness, tests risk, and obvious regressions.\n"
        "- Use Read/Glob/Grep tools for extra context when needed.\n"
        "- verdict must be approved or changes_requested.\n"
        "- issues severity must be critical, major, or minor.\n"
    )

    result = await run_agent_session(
        config=SessionConfig(
            agent_type=AgentType.QA_REVIEWER,
            model=model,
            system_prompt=build_system_prompt(AgentType.QA_REVIEWER, project_path),
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            max_steps=12,
            output_schema=_ReviewSchema,
        ),
        provider=provider,
    )

    if result.outcome != SessionOutcome.COMPLETED or result.structured_output is None:
        return CodeReviewReport(
            verdict="changes_requested",
            issues=[
                CodeReviewIssue(
                    title="Code review inconclusive",
                    severity="major",
                    description=result.error or f"review outcome={result.outcome}",
                )
            ],
            summary="Code review não conseguiu produzir um relatório estruturado.",
        )

    parsed = result.structured_output
    issues = [
        CodeReviewIssue(
            title=issue.title,
            severity=issue.severity,
            description=issue.description,
            file_path=issue.file_path,
        )
        for issue in parsed.issues
    ]
    return CodeReviewReport(
        verdict=parsed.verdict,
        issues=issues,
        summary=parsed.summary,
    )
