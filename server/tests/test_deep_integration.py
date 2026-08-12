"""Phase 12: Luna Debugger Deep Integration — TDD tests."""
from unittest.mock import AsyncMock, Mock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import luna_mcp.server as server_module


@pytest.fixture(autouse=True)
def reset_state():
    orig_bridge = server_module.bridge
    orig_runtime = server_module.runtime
    orig_debugger = server_module.debugger
    yield
    server_module.bridge = orig_bridge
    server_module.runtime = orig_runtime
    server_module.debugger = orig_debugger


@pytest.fixture
def mock_bridge(reset_state):
    bridge = Mock()
    bridge.connected = True
    bridge.eval = AsyncMock(return_value="ok")
    bridge.close = AsyncMock()
    bridge.get_console_messages = Mock(return_value=[])
    bridge._last_seen_console_index = 0
    server_module.bridge = bridge
    return bridge


@pytest.fixture
def mock_runtime(mock_bridge):
    runtime = Mock()
    runtime.call = AsyncMock(return_value="ok")
    server_module.runtime = runtime
    return runtime


# ── Feature 2: get_deep_property ─────────────────────────────────────────────

async def test_get_deep_property_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="5.0")
    from luna_mcp.server import get_deep_property
    result = await get_deep_property("Player", "ParticleSystem", "emission/rateOverTime")
    mock_runtime.call.assert_called_once_with("getDeepProperty", "Player", "ParticleSystem", "emission/rateOverTime")
    assert result == "5.0"


async def test_get_deep_property_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_deep_property
    with pytest.raises(ToolError, match="not initialized"):
        await get_deep_property("Player", "ParticleSystem", "emission/rateOverTime")


async def test_get_deep_property_error_propagated(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: not found")
    from luna_mcp.server import get_deep_property
    result = await get_deep_property("X", "Y", "a/b")
    assert "error" in result


# ── Feature 3: edit_animator_state ───────────────────────────────────────────

async def test_edit_animator_state_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="ok: speed=2.0")
    from luna_mcp.server import edit_animator_state
    result = await edit_animator_state("Player", "12345", "speed", "2.0")
    mock_runtime.call.assert_called_once_with("editAnimatorState", "Player", "12345", "speed", "2.0")
    assert "ok" in result


async def test_edit_animator_state_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import edit_animator_state
    with pytest.raises(ToolError, match="not initialized"):
        await edit_animator_state("Player", "12345", "speed", "2.0")


async def test_edit_animator_state_no_debugger(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: requires Luna Debugger extension")
    from luna_mcp.server import edit_animator_state
    result = await edit_animator_state("Player", "12345", "speed", "2.0")
    assert "error" in result.lower()


# ── Feature 4: log_object / log_component ────────────────────────────────────

async def test_log_object_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="logged to console: Player")
    from luna_mcp.server import log_object
    result = await log_object("Player")
    mock_runtime.call.assert_called_once_with("logObject", "Player")
    assert "logged" in result


async def test_log_object_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import log_object
    with pytest.raises(ToolError, match="not initialized"):
        await log_object("Player")


async def test_log_component_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="logged to console: Player/Rigidbody")
    from luna_mcp.server import log_component
    result = await log_component("Player", "Rigidbody")
    mock_runtime.call.assert_called_once_with("logComponent", "Player", "Rigidbody")
    assert "logged" in result


async def test_log_component_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import log_component
    with pytest.raises(ToolError, match="not initialized"):
        await log_component("Player", "Rigidbody")


# ── Feature 5: debugger_message ──────────────────────────────────────────────

async def test_debugger_message_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value='{"logs": {}}')
    from luna_mcp.server import debugger_message
    result = await debugger_message("GET", "Console", '{"all": true}')
    mock_runtime.call.assert_called_once_with("sendDebuggerMessage", "GET", "Console", '{"all": true}')
    assert result is not None


async def test_debugger_message_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import debugger_message
    with pytest.raises(ToolError, match="not initialized"):
        await debugger_message("GET", "Hierarchy", "{}")


async def test_debugger_message_no_debugger(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: no debugger")
    from luna_mcp.server import debugger_message
    result = await debugger_message("GET", "Hierarchy", "{}")
    assert "error" in result.lower()


# ── Feature 6: get_component_fields ──────────────────────────────────────────

async def test_get_component_fields_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="mass: number\ndrag: number\nangularDrag: number")
    from luna_mcp.server import get_component_fields
    result = await get_component_fields("Rigidbody")
    mock_runtime.call.assert_called_once_with("getComponentFields", "Rigidbody")
    assert "mass" in result


async def test_get_component_fields_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_component_fields
    with pytest.raises(ToolError, match="not initialized"):
        await get_component_fields("Rigidbody")


async def test_get_component_fields_unknown_type(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: not found: FakeComponent")
    from luna_mcp.server import get_component_fields
    result = await get_component_fields("FakeComponent")
    assert "error" in result.lower()


# ── Feature 8: get_console with since param ───────────────────────────────────

async def test_get_console_since_param_filters_new(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[
        {"level": "I", "timestamp": 1000.0, "text": "msg1"},
        {"level": "I", "timestamp": 2000.0, "text": "msg2"},
    ])
    mock_bridge.get_new_console_messages = Mock(return_value=[
        {"level": "I", "timestamp": 2000.0, "text": "msg2"},
    ])
    from luna_mcp.server import get_console
    result = await get_console(count=50, level="", since=1)
    assert "msg2" in result
    # msg1 was before since=1 (index 1 means skip first message)


async def test_get_console_since_zero_returns_all(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[
        {"level": "I", "timestamp": 1000.0, "text": "msg1"},
        {"level": "I", "timestamp": 2000.0, "text": "msg2"},
    ])
    from luna_mcp.server import get_console
    result = await get_console(count=50, level="", since=0)
    assert "msg1" in result
    assert "msg2" in result


async def test_get_console_since_negative_returns_all(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[
        {"level": "I", "timestamp": 1000.0, "text": "msg_a"},
    ])
    from luna_mcp.server import get_console
    result = await get_console(count=50, since=-1)
    assert "msg_a" in result


# ── Feature 9: get_deep_link ──────────────────────────────────────────────────

async def test_get_deep_link_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="gameobject:guid&abc123")
    from luna_mcp.server import get_deep_link
    result = await get_deep_link("Player")
    mock_runtime.call.assert_called_once_with("getDeepLink", "Player", "")
    assert "gameobject:guid&" in result


async def test_get_deep_link_with_component(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="component:guid&abc123&component&45")
    from luna_mcp.server import get_deep_link
    result = await get_deep_link("Player", "Rigidbody")
    mock_runtime.call.assert_called_once_with("getDeepLink", "Player", "Rigidbody")
    assert "component:guid&" in result


async def test_get_deep_link_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_deep_link
    with pytest.raises(ToolError, match="not initialized"):
        await get_deep_link("Player")


# ── Batch registration ────────────────────────────────────────────────────────

def test_new_tools_registered_in_reflection():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.reflection_tools import register_reflection_tools
    mcp = FastMCP("test")
    tools = register_reflection_tools(mcp, AsyncMock())
    assert "get_component_fields" in tools
    assert "log_object" in tools
    assert "log_component" in tools
    assert "debugger_message" in tools


def test_new_tools_registered_in_visual():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.visual_tools import register_visual_tools
    mcp = FastMCP("test")
    tools = register_visual_tools(mcp, AsyncMock(), lambda: None)
    assert "edit_animator_state" in tools
    assert "get_deep_link" in tools


def test_new_tools_registered_in_analysis():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.analysis_tools import register_analysis_tools
    mcp = FastMCP("test")
    tools = register_analysis_tools(mcp, AsyncMock())
    assert "get_deep_property" in tools


def test_get_console_has_since_param():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.batch import derive_params
    from luna_mcp.tools.diagnostics_tools import register_diagnostics_tools
    mcp = FastMCP("test")
    bridge = Mock()
    bridge.get_console_messages = Mock(return_value=[])
    tools = register_diagnostics_tools(mcp, AsyncMock(), AsyncMock(), lambda: bridge)
    fn, params = tools["get_console"]
    resolved = params if params is not None else derive_params(fn)
    assert "since" in resolved
