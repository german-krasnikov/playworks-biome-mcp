"""Tests for get_build_environment, get_startup_timing, luna_report (Phase 18)."""
import json
from unittest.mock import AsyncMock, Mock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import luna_mcp.server as server_module


@pytest.fixture(autouse=True)
def reset_bridge():
    orig_bridge = server_module.bridge
    orig_runtime = server_module.runtime
    orig_debugger = server_module.debugger
    yield
    server_module.bridge = orig_bridge
    server_module.runtime = orig_runtime
    server_module.debugger = orig_debugger


@pytest.fixture
def mock_bridge(reset_bridge):
    bridge = Mock()
    bridge.connected = True
    bridge.eval = AsyncMock(return_value="undefined")
    bridge.get_console_messages = Mock(return_value=[])
    server_module.bridge = bridge
    return bridge


# ── get_build_environment ────────────────────────────────────────────────────

async def test_get_build_environment_success(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value='{"targetPlatform":"develop","buildId":"abc123"}')
    from luna_mcp.server import get_build_environment
    result = await get_build_environment()
    assert "targetPlatform: develop" in result
    assert "buildId: abc123" in result


async def test_get_build_environment_header(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value='{"sdk":"7.1.0"}')
    from luna_mcp.server import get_build_environment
    result = await get_build_environment()
    assert "BUILD ENVIRONMENT" in result


async def test_get_build_environment_empty(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="{}")
    from luna_mcp.server import get_build_environment
    result = await get_build_environment()
    assert "no $environment" in result


async def test_get_build_environment_undefined(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="undefined")
    from luna_mcp.server import get_build_environment
    result = await get_build_environment()
    assert "no $environment" in result


async def test_get_build_environment_parse_error(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="not-json")
    from luna_mcp.server import get_build_environment
    result = await get_build_environment()
    assert "parse error" in result


async def test_get_build_environment_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_build_environment
    with pytest.raises(ToolError, match="not initialized"):
        await get_build_environment()


# ── get_startup_timing ───────────────────────────────────────────────────────

async def test_get_startup_timing_success(mock_bridge):
    payload = json.dumps({
        "timestamps": {"luna:started": 1200, "luna:build": 300},
        "measured": {"loadTime": 900}
    })
    mock_bridge.eval = AsyncMock(return_value=payload)
    from luna_mcp.server import get_startup_timing
    result = await get_startup_timing()
    assert "luna:started" in result
    assert "loadTime" in result


async def test_get_startup_timing_header(mock_bridge):
    payload = json.dumps({"timestamps": {"a": 1}, "measured": {}})
    mock_bridge.eval = AsyncMock(return_value=payload)
    from luna_mcp.server import get_startup_timing
    result = await get_startup_timing()
    assert "STARTUP TIMING" in result


async def test_get_startup_timing_empty(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="{}")
    from luna_mcp.server import get_startup_timing
    result = await get_startup_timing()
    assert "no startup" in result


async def test_get_startup_timing_undefined(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="undefined")
    from luna_mcp.server import get_startup_timing
    result = await get_startup_timing()
    assert "no startup" in result


async def test_get_startup_timing_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_startup_timing
    with pytest.raises(ToolError, match="not initialized"):
        await get_startup_timing()


# ── luna_report ──────────────────────────────────────────────────────────────

async def test_luna_report_debug_captures_console(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="undefined")
    mock_bridge.get_console_messages = Mock(side_effect=[
        [],
        [{"text": "Luna SDK 7.1.0", "level": "I", "timestamp": 0}],
    ])
    from luna_mcp.server import luna_report
    result = await luna_report("debug")
    assert "Luna SDK 7.1.0" in result


async def test_luna_report_startup(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="undefined")
    mock_bridge.get_console_messages = Mock(side_effect=[
        [],
        [{"text": "startup: 200ms", "level": "I", "timestamp": 0}],
    ])
    from luna_mcp.server import luna_report
    result = await luna_report("startup")
    assert "startup: 200ms" in result


async def test_luna_report_unknown_report(mock_bridge):
    from luna_mcp.server import luna_report
    result = await luna_report("invalid")
    assert "unknown report" in result


async def test_luna_report_no_output(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="undefined")
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import luna_report
    result = await luna_report("startup")
    assert "no output" in result


async def test_luna_report_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import luna_report
    with pytest.raises(ToolError, match="not initialized"):
        await luna_report("debug")


async def test_luna_report_eval_exception_graceful(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=Exception("not available"))
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import luna_report
    result = await luna_report("debug")
    assert "not available" in result


# ── get_console per-message length cap ──────────────────────────────────────

def _make_get_console(msgs):
    """Helper: build get_console fn via register_diagnostics_tools with given msgs."""
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.diagnostics_tools import register_diagnostics_tools
    bridge = Mock()
    bridge.get_console_messages = Mock(return_value=msgs)
    ret = register_diagnostics_tools(FastMCP("t"), AsyncMock(), AsyncMock(), lambda: bridge)
    return ret["get_console"][0]


async def test_get_console_truncates_long_message():
    long_text = "X" * 2000
    msgs = [{"text": long_text, "level": "E", "timestamp": 0}]
    fn = _make_get_console(msgs)
    result = await fn()
    assert long_text not in result
    assert "X" * 200 in result
    assert "chars" in result  # truncation marker present


async def test_get_console_keeps_short_message_intact():
    msgs = [{"text": "hi", "level": "I", "timestamp": 0}]
    fn = _make_get_console(msgs)
    result = await fn()
    assert "hi" in result
    assert "chars" not in result  # no truncation marker


async def test_get_console_cap_is_per_message():
    long_text = "A" * 2000
    msgs = [
        {"text": long_text, "level": "E", "timestamp": 0},
        {"text": long_text, "level": "W", "timestamp": 0},
    ]
    fn = _make_get_console(msgs)
    result = await fn()
    # both messages are independently truncated — two markers
    assert result.count("chars") == 2
