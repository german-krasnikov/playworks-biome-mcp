from unittest.mock import AsyncMock

import pytest

from luna_mcp.tools.batch import (
    _TOOL_REGISTRY,
    coerce_args,
    execute_batch,
    parse_command,
    register_batch_tool,
)

# ── parse_command ────────────────────────────────────────────────────────────

def test_parse_command_simple():
    cmd, kwargs = parse_command("get_hierarchy depth=2")
    assert cmd == "get_hierarchy"
    assert kwargs == {"depth": "2"}


def test_parse_command_no_args():
    cmd, kwargs = parse_command("ping")
    assert cmd == "ping"
    assert kwargs == {}


def test_parse_command_quoted_value():
    cmd, kwargs = parse_command('find_objects query="Main Camera"')
    assert cmd == "find_objects"
    assert kwargs == {"query": "Main Camera"}


def test_parse_command_empty_raises():
    with pytest.raises(ValueError, match="Empty command"):
        parse_command("")


def test_parse_command_no_equals_raises():
    with pytest.raises(ValueError, match="no ="):
        parse_command("get_hierarchy 2")


# ── coerce_args ──────────────────────────────────────────────────────────────

def test_coerce_args_int():
    result = coerce_args({"depth": "2"}, {"depth": int})
    assert result == {"depth": 2}


def test_coerce_args_float():
    result = coerce_args({"x": "1.5"}, {"x": float})
    assert result == {"x": 1.5}


def test_coerce_args_bool_true():
    result = coerce_args({"active": "true"}, {"active": bool})
    assert result == {"active": True}


def test_coerce_args_bool_false():
    result = coerce_args({"active": "false"}, {"active": bool})
    assert result == {"active": False}


def test_coerce_args_unknown_key_stays_string():
    result = coerce_args({"foo": "bar"}, {"depth": int})
    assert result == {"foo": "bar"}


# ── execute_batch ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate registry between tests."""
    original = dict(_TOOL_REGISTRY)
    yield
    _TOOL_REGISTRY.clear()
    _TOOL_REGISTRY.update(original)


async def test_execute_batch_single_command():
    handler = AsyncMock(return_value="pong")
    register_batch_tool("ping", handler, {})
    result = await execute_batch("ping")
    assert "--- ping ---" in result
    assert "pong" in result
    handler.assert_called_once_with()


async def test_execute_batch_multiple_commands():
    ping_handler = AsyncMock(return_value="pong")
    hier_handler = AsyncMock(return_value="Root [Scene]")
    register_batch_tool("ping", ping_handler, {})
    register_batch_tool("get_hierarchy", hier_handler, {"depth": int})
    result = await execute_batch("ping\nget_hierarchy depth=2")
    assert "--- ping ---" in result
    assert "--- get_hierarchy ---" in result
    assert "pong" in result
    assert "Root [Scene]" in result
    hier_handler.assert_called_once_with(depth=2)


async def test_execute_batch_continue_on_error():
    fail_handler = AsyncMock(side_effect=RuntimeError("boom"))
    ok_handler = AsyncMock(return_value="ok")
    register_batch_tool("fail", fail_handler, {})
    register_batch_tool("ok_cmd", ok_handler, {})
    result = await execute_batch("fail\nok_cmd", mode="continue")
    assert "error: boom" in result
    assert "ok" in result


async def test_execute_batch_stop_on_error():
    fail_handler = AsyncMock(side_effect=RuntimeError("boom"))
    ok_handler = AsyncMock(return_value="ok")
    register_batch_tool("fail", fail_handler, {})
    register_batch_tool("ok_cmd", ok_handler, {})
    result = await execute_batch("fail\nok_cmd", mode="stop")
    assert "error: boom" in result
    ok_handler.assert_not_called()


async def test_execute_batch_unknown_command():
    result = await execute_batch("nonexistent_cmd")
    assert "error:" in result
    assert "nonexistent_cmd" in result or "Unknown command" in result
