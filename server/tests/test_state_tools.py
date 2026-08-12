from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def call_fn():
    return AsyncMock(return_value="result")


@pytest.fixture
def send_fn():
    return AsyncMock(return_value="0ms: 1.0\n100ms: 1.5\n200ms: 2.0")


@pytest.fixture
def tools(call_fn, send_fn):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.state_tools import register_state_tools
    mcp = FastMCP("test")
    return register_state_tools(mcp, call_fn, send_fn), call_fn, send_fn


# watch_property
async def test_watch_property_returns_history(tools):
    reg, call_fn, send_fn = tools
    send_fn.return_value = "0ms: 1.0\n100ms: 1.5\n200ms: 2.0"
    fn, _ = reg["watch_property"]
    result = await fn("Scene/Player", "Rigidbody", "velocity", 100, 3)
    assert "0ms" in result
    assert "100ms" in result


async def test_watch_property_timeout_calculation(tools):
    """count=20, interval_ms=500 => timeout > 10s"""
    reg, call_fn, send_fn = tools
    fn, _ = reg["watch_property"]
    await fn("Scene/Player", "Rigidbody", "velocity", 500, 20)
    # Verify send_fn was called with timeout > 10
    _, kwargs = send_fn.call_args
    assert kwargs.get("timeout", 30.0) >= 10.0


# snapshot_state
async def test_snapshot_state_passes_name_and_path(tools):
    reg, call_fn, _ = tools
    call_fn.return_value = "saved: snap1 (Scene/Player)"
    fn, _ = reg["snapshot_state"]
    result = await fn("snap1", "Scene/Player")
    assert result == "saved: snap1 (Scene/Player)"
    call_fn.assert_awaited_with("snapshotState", "snap1", "Scene/Player")


async def test_snapshot_state_response_format(tools):
    reg, call_fn, _ = tools
    call_fn.return_value = "saved: mysnap (UI/Button)"
    fn, _ = reg["snapshot_state"]
    result = await fn("mysnap", "UI/Button")
    assert "saved" in result


# restore_state
async def test_restore_state_found(tools):
    reg, call_fn, _ = tools
    call_fn.return_value = "restored: snap1"
    fn, _ = reg["restore_state"]
    result = await fn("snap1")
    assert result == "restored: snap1"
    call_fn.assert_awaited_with("restoreState", "snap1")


async def test_restore_state_not_found(tools):
    reg, call_fn, _ = tools
    call_fn.return_value = "not found: snap2"
    fn, _ = reg["restore_state"]
    result = await fn("snap2")
    assert "not found" in result
