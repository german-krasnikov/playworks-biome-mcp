from unittest.mock import AsyncMock, Mock

import pytest

from luna_mcp.debugger import Debugger


@pytest.fixture
def mock_bridge():
    bridge = Mock()
    bridge._debugger_paused = None
    bridge.send_cdp = AsyncMock(return_value={"result": {}})
    return bridge


@pytest.fixture
def debugger(mock_bridge):
    return Debugger(mock_bridge)


# ── enable ──────────────────────────────────────────────────────────────────

async def test_enable_sends_debugger_enable(debugger, mock_bridge):
    await debugger.enable()
    mock_bridge.send_cdp.assert_called_once_with("Debugger.enable")


async def test_enable_only_once(debugger, mock_bridge):
    await debugger.enable()
    await debugger.enable()
    assert mock_bridge.send_cdp.call_count == 1


# ── set_breakpoint ───────────────────────────────────────────────────────────

async def test_set_breakpoint_sends_command(debugger, mock_bridge):
    mock_bridge.send_cdp.return_value = {
        "result": {"breakpointId": "1:41:0:.*Player\\.js"}
    }
    bp_id = await debugger.set_breakpoint(".*Player\\.js", 42)
    calls = mock_bridge.send_cdp.call_args_list
    methods = [c[0][0] for c in calls]
    assert "Debugger.setBreakpointByUrl" in methods


async def test_set_breakpoint_returns_id(debugger, mock_bridge):
    mock_bridge.send_cdp.return_value = {
        "result": {"breakpointId": "1:41:0:.*Player\\.js"}
    }
    bp_id = await debugger.set_breakpoint(".*Player\\.js", 42)
    assert bp_id == "1:41:0:.*Player\\.js"


async def test_set_breakpoint_line_is_zero_indexed(debugger, mock_bridge):
    mock_bridge.send_cdp.return_value = {"result": {"breakpointId": "x"}}
    await debugger.set_breakpoint(".*Player\\.js", 42)
    set_bp_call = next(
        c for c in mock_bridge.send_cdp.call_args_list
        if c[0][0] == "Debugger.setBreakpointByUrl"
    )
    assert set_bp_call[0][1]["lineNumber"] == 41  # 42 - 1


# ── remove_breakpoint ────────────────────────────────────────────────────────

async def test_remove_breakpoint_sends_command(debugger, mock_bridge):
    await debugger.remove_breakpoint("1:41:0:.*Player\\.js")
    mock_bridge.send_cdp.assert_called_once_with(
        "Debugger.removeBreakpoint",
        {"breakpointId": "1:41:0:.*Player\\.js"},
    )


# ── pause / resume ───────────────────────────────────────────────────────────

async def test_pause_sends_command(debugger, mock_bridge):
    await debugger.pause()
    methods = [c[0][0] for c in mock_bridge.send_cdp.call_args_list]
    assert "Debugger.pause" in methods


async def test_resume_sends_command_and_clears_state(debugger, mock_bridge):
    mock_bridge._debugger_paused = {"callFrames": []}
    await debugger.resume()
    methods = [c[0][0] for c in mock_bridge.send_cdp.call_args_list]
    assert "Debugger.resume" in methods
    assert mock_bridge._debugger_paused is None


# ── get_call_stack ───────────────────────────────────────────────────────────

def test_get_call_stack_not_paused(debugger, mock_bridge):
    mock_bridge._debugger_paused = None
    assert debugger.get_call_stack() == "(not paused)"


def test_get_call_stack_formats_frames(debugger, mock_bridge):
    mock_bridge._debugger_paused = {
        "callFrames": [
            {
                "functionName": "PlayerUpdate",
                "location": {"scriptId": "42", "lineNumber": 10, "columnNumber": 0},
                "url": "http://127.0.0.1:8000/Player.js",
                "scopeChain": [],
            },
            {
                "functionName": "",
                "location": {"scriptId": "1", "lineNumber": 119, "columnNumber": 0},
                "url": "http://127.0.0.1:8000/main.js",
                "scopeChain": [],
            },
        ]
    }
    result = debugger.get_call_stack()
    assert "#0 PlayerUpdate (Player.js:11)" in result
    assert "#1 (anonymous) (main.js:120)" in result


def test_get_call_stack_empty_frames(debugger, mock_bridge):
    mock_bridge._debugger_paused = {"callFrames": []}
    assert debugger.get_call_stack() == "(empty stack)"


# ── get_scope_variables ──────────────────────────────────────────────────────

async def test_get_scope_variables_not_paused(debugger, mock_bridge):
    mock_bridge._debugger_paused = None
    result = await debugger.get_scope_variables()
    assert result == "(not paused)"


async def test_get_scope_variables_frame_out_of_range(debugger, mock_bridge):
    mock_bridge._debugger_paused = {"callFrames": []}
    result = await debugger.get_scope_variables(frame_index=0)
    assert "frame 0 not found" in result


async def test_get_scope_variables_no_local_scope(debugger, mock_bridge):
    mock_bridge._debugger_paused = {
        "callFrames": [{"scopeChain": [{"type": "global", "object": {"objectId": "g"}}]}]
    }
    result = await debugger.get_scope_variables()
    assert result == "(no local scope)"


async def test_get_scope_variables_returns_properties(debugger, mock_bridge):
    mock_bridge._debugger_paused = {
        "callFrames": [
            {
                "scopeChain": [
                    {"type": "local", "object": {"objectId": "scope:0:0"}},
                ]
            }
        ]
    }
    mock_bridge.send_cdp.return_value = {
        "result": {
            "result": [
                {"name": "speed", "value": {"type": "number", "value": 4.2}},
                {"name": "health", "value": {"type": "number", "value": 100}},
                {"name": "isAlive", "value": {"type": "boolean", "value": True}},
                {"name": "name", "value": {"type": "string", "value": "Player"}},
            ]
        }
    }
    result = await debugger.get_scope_variables()
    assert "speed: 4.2" in result
    assert "health: 100" in result
    assert "isAlive: True" in result
    assert "name: Player" in result
    mock_bridge.send_cdp.assert_called_once_with(
        "Runtime.getProperties",
        {"objectId": "scope:0:0", "ownProperties": True},
    )
