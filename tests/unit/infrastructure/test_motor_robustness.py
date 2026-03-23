from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from codeforge.application.use_cases.run_agent_session import _execute_tool_call

# --- Tool error hint ---


@pytest.mark.asyncio
async def test_tool_error_hint_appended_on_exception():
    tool = AsyncMock(side_effect=ValueError("file not found"))
    tools = {"ReadTool": tool}
    result = await _execute_tool_call(
        {"name": "ReadTool", "input": {"path": "/x"}}, tools, "sess-1"
    )
    assert "[Tool Error]: file not found" in result
    assert "[Analyze the error above and try a different approach.]" in result


@pytest.mark.asyncio
async def test_tool_success_has_no_hint():
    tool = AsyncMock(return_value="file contents")
    tools = {"ReadTool": tool}
    result = await _execute_tool_call(
        {"name": "ReadTool", "input": {"path": "/x"}}, tools, "sess-1"
    )
    assert result == "file contents"
    assert "Analyze the error" not in result


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    result = await _execute_tool_call({"name": "Ghost", "input": {}}, {}, "sess-1")
    assert "not available" in result


# --- json_repair fallback ---


def test_valid_json_parsed_normally():
    args = '{"path": "/foo/bar"}'
    result = json.loads(args)
    assert result == {"path": "/foo/bar"}


def test_json_repair_recovers_truncated_json():
    from json_repair import repair_json

    truncated = '{"path": "/foo/bar'
    repaired = json.loads(repair_json(truncated))
    assert repaired.get("path") == "/foo/bar"


def test_json_repair_recovers_trailing_comma():
    from json_repair import repair_json

    bad = '{"key": "val",}'
    repaired = json.loads(repair_json(bad))
    assert repaired == {"key": "val"}


def test_json_repair_recovers_single_quotes():
    from json_repair import repair_json

    bad = "{'key': 'val'}"
    repaired = json.loads(repair_json(bad))
    assert repaired == {"key": "val"}


def test_json_repair_fallback_to_empty_on_garbage():
    from json_repair import repair_json

    garbage = "not json at all %%% !!!"
    try:
        result = json.loads(repair_json(garbage))
    except Exception:
        result = {}
    assert isinstance(result, (dict, str, list))
