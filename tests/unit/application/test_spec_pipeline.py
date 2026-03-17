from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from codeforge.application.dto.agent_session_dto import SessionResult
from codeforge.application.use_cases.run_spec_pipeline import (
    _PHASE_SEQUENCES,
    _build_phase_prompt,
    _extract_last_assistant_text,
    run_spec_pipeline,
)
from codeforge.domain.entities.agent import SessionOutcome, TokenUsage
from codeforge.domain.entities.spec import ComplexityTier, SpecPhase
from codeforge.domain.value_objects.model_id import ModelId


def _make_model() -> ModelId:
    return ModelId("anthropic:claude-sonnet-4-20250514")


def _ok_result(tool_calls: int = 1) -> SessionResult:
    return SessionResult(
        outcome=SessionOutcome.COMPLETED,
        tool_call_count=tool_calls,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        messages=[{"role": "assistant", "content": "Done."}],
    )


def _failed_result(outcome: SessionOutcome = SessionOutcome.ERROR) -> SessionResult:
    return SessionResult(
        outcome=outcome,
        usage=TokenUsage(),
    )


# ── Phase sequences ──────────────────────────────────────────────────────────


def test_simple_phase_sequence_has_two_phases():
    assert _PHASE_SEQUENCES[ComplexityTier.SIMPLE] == [SpecPhase.WRITING, SpecPhase.VALIDATION]


def test_standard_phase_sequence_has_four_phases():
    phases = _PHASE_SEQUENCES[ComplexityTier.STANDARD]
    assert len(phases) == 4
    assert SpecPhase.DISCOVERY in phases
    assert SpecPhase.WRITING in phases


def test_complex_phase_sequence_has_seven_phases():
    phases = _PHASE_SEQUENCES[ComplexityTier.COMPLEX]
    assert len(phases) == 7
    assert SpecPhase.RESEARCH in phases
    assert SpecPhase.CRITIQUE in phases


# ── Prompt builder ────────────────────────────────────────────────────────────


def test_phase_prompt_contains_task_description():
    prompt = _build_phase_prompt(
        phase=SpecPhase.WRITING,
        task_description="Add auth JWT",
        accumulated_context=[],
        force_tool_use=False,
    )
    assert "Add auth JWT" in prompt


def test_phase_prompt_includes_prior_context():
    prompt = _build_phase_prompt(
        phase=SpecPhase.REQUIREMENTS,
        task_description="task",
        accumulated_context=["[DISCOVERY]\nFound routes.py"],
        force_tool_use=False,
    )
    assert "Prior Phase Outputs" in prompt
    assert "Found routes.py" in prompt


def test_phase_prompt_force_tool_use_appends_suffix():
    prompt = _build_phase_prompt(
        phase=SpecPhase.WRITING,
        task_description="task",
        accumulated_context=[],
        force_tool_use=True,
    )
    assert "MUST use the available tools" in prompt


def test_extract_last_assistant_text_finds_last_message():
    messages = [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "first response"},
        {"role": "tool", "content": "result"},
        {"role": "assistant", "content": "final response"},
    ]
    result = _extract_last_assistant_text(messages)
    assert result == "final response"


def test_extract_last_assistant_text_returns_none_if_no_assistant():
    messages = [{"role": "user", "content": "hi"}]
    assert _extract_last_assistant_text(messages) is None


# ── Full pipeline ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simple_pipeline_calls_two_phases(tmp_path: Path):
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t1",
            task_description="Add JWT auth",
            complexity=ComplexityTier.SIMPLE,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert call_count == 2
    assert result.phases_completed == 2


@pytest.mark.asyncio
async def test_standard_pipeline_calls_four_phases(tmp_path: Path):
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t2",
            task_description="Add caching layer",
            complexity=ComplexityTier.STANDARD,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert call_count == 4


@pytest.mark.asyncio
async def test_complex_pipeline_calls_seven_phases(tmp_path: Path):
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t3",
            task_description="Rewrite auth system",
            complexity=ComplexityTier.COMPLEX,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert call_count == 7


@pytest.mark.asyncio
async def test_phase_retry_when_no_tool_calls(tmp_path: Path):
    """Phase is retried when tool_call_count == 0 on first attempt."""
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        # First call: no tool calls; second call: OK
        return _ok_result(tool_calls=0 if call_count == 1 else 1)

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t4",
            task_description="task",
            complexity=ComplexityTier.SIMPLE,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    # First phase retried once (2 calls), second phase normal (1 call)
    assert call_count == 3


@pytest.mark.asyncio
async def test_phase_fails_after_max_retries_returns_failure(tmp_path: Path):
    async def mock_session(config, provider):
        return _failed_result(SessionOutcome.ERROR)

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t5",
            task_description="task",
            complexity=ComplexityTier.SIMPLE,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is False
    assert result.error is not None
    assert result.phases_completed == 0


@pytest.mark.asyncio
async def test_cancelled_before_first_phase(tmp_path: Path):
    event = asyncio.Event()
    event.set()

    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t6",
            task_description="task",
            complexity=ComplexityTier.SIMPLE,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
            abort_event=event,
        )

    assert result.success is False
    assert result.error == "Cancelled"
    assert call_count == 0


@pytest.mark.asyncio
async def test_spec_content_read_from_file(tmp_path: Path):
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# My Spec\n\nDetailed content here.")

    async def mock_session(config, provider):
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t7",
            task_description="task",
            complexity=ComplexityTier.SIMPLE,
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.spec is not None
    assert "My Spec" in result.spec.content


@pytest.mark.asyncio
async def test_usage_accumulated_across_phases(tmp_path: Path):
    async def mock_session(config, provider):
        return SessionResult(
            outcome=SessionOutcome.COMPLETED,
            tool_call_count=1,
            usage=TokenUsage(input_tokens=200, output_tokens=100),
            messages=[],
        )

    with patch(
        "codeforge.application.use_cases.run_spec_pipeline.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_spec_pipeline(
            task_id="t8",
            task_description="task",
            complexity=ComplexityTier.SIMPLE,  # 2 phases
            model=_make_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.total_usage.input_tokens == 400  # 200 per phase × 2
    assert result.total_usage.output_tokens == 200
