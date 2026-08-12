"""Phase 11b: Bridge.Reflection + Object Selection — TDD tests."""
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
    bridge.eval = AsyncMock(return_value="ok")
    bridge.close = AsyncMock()
    server_module.bridge = bridge
    return bridge


@pytest.fixture
def mock_runtime(mock_bridge):
    runtime = Mock()
    runtime.call = AsyncMock(return_value="ok")
    server_module.runtime = runtime
    return runtime


# ── get_enums ────────────────────────────────────────────────────────────────

async def test_get_enums_no_filter(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="LightType: Spot=0, Directional=1")
    from luna_mcp.server import get_enums
    result = await get_enums()
    mock_runtime.call.assert_called_once_with("getEnums", "")
    assert "LightType" in result


async def test_get_enums_with_filter(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="LightType: Spot=0, Directional=1")
    from luna_mcp.server import get_enums
    result = await get_enums(filter="Light")
    mock_runtime.call.assert_called_once_with("getEnums", "Light")
    assert "LightType" in result


async def test_get_enums_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_enums
    with pytest.raises(ToolError, match="not initialized"):
        await get_enums()


# ── get_type_info ────────────────────────────────────────────────────────────

async def test_get_type_info_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="type: Rigidbody\nkind: class\nfields: mass")
    from luna_mcp.server import get_type_info
    result = await get_type_info(type_name="Rigidbody")
    mock_runtime.call.assert_called_once_with("getTypeInfo", "Rigidbody")
    assert "Rigidbody" in result


async def test_get_type_info_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_type_info
    with pytest.raises(ToolError, match="not initialized"):
        await get_type_info(type_name="Rigidbody")


# ── get_assemblies ───────────────────────────────────────────────────────────

async def test_get_assemblies_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="UnityEngine\nAssembly-CSharp")
    from luna_mcp.server import get_assemblies
    result = await get_assemblies()
    mock_runtime.call.assert_called_once_with("getAssemblies")
    assert "UnityEngine" in result


async def test_get_assemblies_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_assemblies
    with pytest.raises(ToolError, match="not initialized"):
        await get_assemblies()


# ── select_object ────────────────────────────────────────────────────────────

async def test_select_object_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="selected: Canvas/Button")
    from luna_mcp.server import select_object
    result = await select_object(path="Canvas/Button")
    mock_runtime.call.assert_called_once_with("selectObject", "Canvas/Button")
    assert "selected" in result


async def test_select_object_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import select_object
    with pytest.raises(ToolError, match="not initialized"):
        await select_object(path="Canvas/Button")


# ── get_selection ────────────────────────────────────────────────────────────

async def test_get_selection_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="type: GameObject\npath: Canvas\nguid: abc123")
    from luna_mcp.server import get_selection
    result = await get_selection()
    mock_runtime.call.assert_called_once_with("getSelection")
    assert "GameObject" in result


async def test_get_selection_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_selection
    with pytest.raises(ToolError, match="not initialized"):
        await get_selection()


# ── batch registration ───────────────────────────────────────────────────────

def test_all_tools_registered_for_batch():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.reflection_tools import register_reflection_tools
    mcp = FastMCP("test")
    call_fn = AsyncMock()
    tools = register_reflection_tools(mcp, call_fn)
    expected = {"get_enums", "get_type_info", "get_assemblies", "select_object", "get_selection",
                "get_component_fields", "log_object", "log_component", "debugger_message"}
    assert expected == set(tools.keys())
