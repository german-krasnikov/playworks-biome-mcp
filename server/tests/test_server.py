from unittest.mock import AsyncMock, Mock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import luna_mcp.server as server_module
from luna_mcp.server import _send


@pytest.fixture(autouse=True)
def reset_bridge():
    """Reset module-level bridge, runtime, debugger after each test."""
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
    bridge.eval = AsyncMock(return_value="pong")
    bridge.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")
    bridge.close = AsyncMock()
    server_module.bridge = bridge
    return bridge


# ── _send helper ────────────────────────────────────────────────────────────

async def test_send_connected_returns_result(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="42")
    result = await _send("1+1")
    assert result == "42"


async def test_send_not_initialized_raises_tool_error():
    server_module.bridge = None
    with pytest.raises(ToolError, match="not initialized"):
        await _send("x")


async def test_send_bridge_disconnected_auto_connects(mock_bridge):
    mock_bridge.connected = False
    mock_bridge.connect = AsyncMock(side_effect=ConnectionError("no chrome"))
    mock_bridge.enable_console = AsyncMock()
    with pytest.raises(ToolError, match="not connected"):
        await _send("x")


async def test_send_js_error_raises_tool_error(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=RuntimeError("ReferenceError: x is not defined"))
    with pytest.raises(ToolError, match="JS error"):
        await _send("x")


async def test_send_cdp_error_raises_tool_error(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=ConnectionError("WebSocket closed"))
    with pytest.raises(ToolError, match="CDP error"):
        await _send("x")


# ── Phase 10: Enhanced error messages ────────────────────────────────────────

async def test_send_js_error_includes_expression(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=RuntimeError("ReferenceError"))
    with pytest.raises(ToolError) as exc_info:
        await _send("someExpression()")
    assert "expr:" in str(exc_info.value)
    assert "someExpression" in str(exc_info.value)


async def test_send_long_expression_truncated(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=RuntimeError("err"))
    long_expr = "x" * 150
    with pytest.raises(ToolError) as exc_info:
        await _send(long_expr)
    assert "..." in str(exc_info.value)


async def test_send_short_expression_no_ellipsis(mock_bridge):
    mock_bridge.eval = AsyncMock(side_effect=RuntimeError("err"))
    with pytest.raises(ToolError) as exc_info:
        await _send("short()")
    assert "..." not in str(exc_info.value)


# ── Phase 10: Configurable timeout for eval_js ────────────────────────────────

async def test_eval_js_default_timeout_passes_30(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="42")
    from luna_mcp.server import eval_js
    await eval_js("1+1")
    mock_bridge.eval.assert_called_once_with("1+1", timeout=30.0)


async def test_eval_js_custom_timeout(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="42")
    from luna_mcp.server import eval_js
    await eval_js("1+1", timeout=60.0)
    mock_bridge.eval.assert_called_once_with("1+1", timeout=60.0)


# ── Phase 10: get_connection_info tool ───────────────────────────────────────

async def test_get_connection_info_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import get_connection_info
    with pytest.raises(ToolError, match="not initialized"):
        await get_connection_info()


async def test_get_connection_info_disconnected(mock_bridge):
    mock_bridge.connected = False
    mock_bridge._port = 9222
    from luna_mcp.server import get_connection_info
    result = await get_connection_info()
    assert "port: 9222" in result
    assert "connected: False" in result


async def test_get_connection_info_connected(mock_bridge):
    mock_bridge._port = 9222
    mock_bridge.eval = AsyncMock(side_effect=["http://localhost/", "Luna Build", "0.3.0", "available"])
    from luna_mcp.server import get_connection_info
    result = await get_connection_info()
    assert "port: 9222" in result
    assert "connected: True" in result
    assert "page_url:" in result
    assert "page_title:" in result
    assert "helpers:" in result
    assert "debugger:" in result


async def test_get_connection_info_eval_fails_graceful(mock_bridge):
    mock_bridge._port = 9222
    mock_bridge.eval = AsyncMock(side_effect=RuntimeError("no page"))
    from luna_mcp.server import get_connection_info
    result = await get_connection_info()
    assert "port: 9222" in result
    assert "(error" in result or "unknown" in result


# ── Phase 10: list_pages tool ────────────────────────────────────────────────

async def test_list_pages_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import list_pages
    with pytest.raises(ToolError, match="not initialized"):
        await list_pages()


async def test_list_pages_no_pages(mock_bridge):
    mock_bridge.discover_pages = AsyncMock(return_value=[])
    from luna_mcp.server import list_pages
    result = await list_pages()
    assert "(no pages found)" in result


async def test_list_pages_returns_formatted_lines(mock_bridge):
    mock_bridge.discover_pages = AsyncMock(return_value=[
        {"type": "page", "title": "Luna Build", "url": "http://localhost/index.html"},
        {"type": "other", "title": "DevTools", "url": "devtools://devtools/..."},
    ])
    from luna_mcp.server import list_pages
    result = await list_pages()
    assert "[page] Luna Build - http://localhost/index.html" in result
    assert "[other] DevTools" in result


async def test_list_pages_connection_refused_raises(mock_bridge):
    mock_bridge.discover_pages = AsyncMock(side_effect=Exception("Connection refused"))
    from luna_mcp.server import list_pages
    with pytest.raises(ToolError, match="Cannot reach Chrome"):
        await list_pages()


async def test_list_pages_port_override(mock_bridge):
    mock_bridge.discover_pages = AsyncMock(return_value=[])
    mock_bridge._port = 9222
    from luna_mcp.server import list_pages
    await list_pages(port=9333)
    assert mock_bridge._port == 9222  # port restored after discovery


# ── Phase 10: find_objects_by_component tool ─────────────────────────────────

async def test_find_objects_by_component_returns_paths(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="Player\nCamera/CameraRig")
    from luna_mcp.server import find_objects_by_component
    result = await find_objects_by_component("Camera")
    assert "Player" in result
    mock_runtime.call.assert_called_once_with("findByComponent", "Camera")


async def test_find_objects_by_component_no_matches(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="no matches")
    from luna_mcp.server import find_objects_by_component
    result = await find_objects_by_component("NonExistent")
    assert result == "no matches"


async def test_find_objects_by_component_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import find_objects_by_component
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await find_objects_by_component("Camera")


async def test_call_error_includes_method_name(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(side_effect=RuntimeError("JS fail"))
    from luna_mcp.server import _call
    with pytest.raises(ToolError) as exc_info:
        await _call("getHierarchy", 3)
    assert "getHierarchy" in str(exc_info.value)


# ── Tools ────────────────────────────────────────────────────────────────────

async def test_ping_returns_pong(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="pong")
    from luna_mcp.server import ping
    result = await ping()
    assert result == "pong"


async def test_eval_js_returns_result(mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="42")
    from luna_mcp.server import eval_js
    result = await eval_js("1+41")
    assert result == "42"


async def test_screenshot_saves_file(mock_bridge, tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    from luna_mcp.server import screenshot
    result = await screenshot()
    assert "luna_screenshot" in result
    # Extension depends on SCREENSHOT_FORMAT config (jpeg → .jpg, png → .png)
    from luna_mcp.config import SCREENSHOT_FORMAT
    ext = ".jpg" if SCREENSHOT_FORMAT == "jpeg" else ".png"
    assert (tmp_path / f"luna_screenshot{ext}").exists()


async def test_screenshot_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import screenshot
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await screenshot()


# ── get_hierarchy tool ───────────────────────────────────────────────────────

@pytest.fixture
def mock_runtime():
    rt = Mock()
    rt.call = AsyncMock(return_value="Main Camera [Camera]\nPlayer [Rigidbody]")
    return rt


async def test_get_hierarchy_returns_tree(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    from luna_mcp.server import get_hierarchy
    result = await get_hierarchy()
    assert "Main Camera" in result
    mock_runtime.call.assert_called_once()


async def test_get_hierarchy_default_depth(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    from luna_mcp.server import get_hierarchy
    await get_hierarchy()
    args = mock_runtime.call.call_args[0]
    assert args[0] == "getHierarchy"
    assert args[1] == 3  # default depth


async def test_get_hierarchy_custom_depth_and_root(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    from luna_mcp.server import get_hierarchy
    await get_hierarchy(depth=5, root="Player")
    args = mock_runtime.call.call_args[0]
    assert args[1] == 5
    assert args[2] == "Player"


async def test_get_hierarchy_not_connected_raises(mock_runtime):
    server_module.bridge = None
    server_module.runtime = mock_runtime
    from luna_mcp.server import get_hierarchy
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_hierarchy()


# ── _call helper ─────────────────────────────────────────────────────────────

async def test_call_helper_connected(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="ok")
    from luna_mcp.server import _call
    result = await _call("getHierarchy", 3, "")
    mock_runtime.call.assert_called_once_with("getHierarchy", 3, "")
    assert result == "ok"


async def test_call_helper_not_connected():
    server_module.bridge = None
    from luna_mcp.server import _call
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await _call("getHierarchy")


async def test_call_helper_js_error(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(side_effect=RuntimeError("ReferenceError"))
    from luna_mcp.server import _call
    with pytest.raises(ToolError, match="JS error"):
        await _call("getHierarchy")


# ── get_component tool ────────────────────────────────────────────────────────

async def test_get_component_returns_properties(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="MovementSpeed: 4.2\nIsMovementEnabled: true")
    from luna_mcp.server import get_component
    result = await get_component("Player", "Movement_V1")
    assert "MovementSpeed: 4.2" in result
    mock_runtime.call.assert_called_once_with("getComponent", "Player", "Movement_V1")


async def test_get_component_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_component
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_component("Player", "Movement_V1")


# ── get_components_list tool ──────────────────────────────────────────────────

async def test_get_components_list_returns_types(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="Rigidbody\nCapsuleCollider")
    from luna_mcp.server import get_components_list
    result = await get_components_list("Player")
    assert "Rigidbody" in result
    mock_runtime.call.assert_called_once_with("getComponents", "Player")


async def test_get_components_list_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_components_list
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_components_list("Player")


# ── get_object_detail tool ────────────────────────────────────────────────────

async def test_get_object_detail_returns_full_dump(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    full_dump = "--- Transform ---\nposition: (0.0, 0.0, 0.0)\n\n--- Rigidbody ---\nmass: 1"
    mock_runtime.call = AsyncMock(return_value=full_dump)
    from luna_mcp.server import get_object_detail
    result = await get_object_detail("Player")
    assert "--- Transform ---" in result
    assert "--- Rigidbody ---" in result
    mock_runtime.call.assert_called_once_with("getObjectDetail", "Player")


async def test_get_object_detail_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_object_detail
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_object_detail("Player")


# ── get_console tool ──────────────────────────────────────────────────────────

async def test_get_console_returns_formatted_lines(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[
        {"level": "E", "timestamp": 1609459200000, "text": "NullRef at Player.js:47"},
        {"level": "W", "timestamp": 1609459100000, "text": "Physics issue"},
    ])
    from luna_mcp.server import get_console
    result = await get_console()
    assert "[E " in result
    assert "NullRef at Player.js:47" in result
    assert "[W " in result
    assert "Physics issue" in result


async def test_get_console_empty_returns_placeholder(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import get_console
    result = await get_console()
    assert result == "(no console messages)"


async def test_get_console_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_console
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_console()


async def test_get_console_passes_count_and_level(mock_bridge):
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import get_console
    await get_console(count=10, level="E")
    mock_bridge.get_console_messages.assert_called_once_with(10, "E")


# ── Phase 4: on_reconnect callback ──────────────────────────────────────────

async def test_on_reconnect_resets_runtime_injected():
    """lifespan wires _on_reconnect: callback resets runtime._injected to False."""
    from luna_mcp.cdp_bridge import CDPBridge
    from luna_mcp.luna_runtime import LunaRuntime

    bridge = CDPBridge()
    runtime = LunaRuntime(bridge)
    runtime._injected = True

    # Simulate the callback wired in lifespan
    bridge.enable_console = AsyncMock()

    async def _on_reconnect():
        runtime._injected = False
        try:
            await bridge.enable_console()
        except Exception:
            pass

    bridge._on_reconnect = _on_reconnect
    await bridge._on_reconnect()

    assert runtime._injected is False
    bridge.enable_console.assert_called_once()


# ── Phase 5: _parse_value ────────────────────────────────────────────────────

def test_parse_value_int():
    from luna_mcp.server import _parse_value
    assert _parse_value("42") == 42


def test_parse_value_float():
    from luna_mcp.server import _parse_value
    assert _parse_value("3.14") == 3.14


def test_parse_value_bool_true():
    from luna_mcp.server import _parse_value
    assert _parse_value("true") is True


def test_parse_value_bool_false():
    from luna_mcp.server import _parse_value
    assert _parse_value("false") is False


def test_parse_value_string():
    from luna_mcp.server import _parse_value
    assert _parse_value("hello") == "hello"


# ── Phase 5: set_property tool ───────────────────────────────────────────────

async def test_set_property_returns_ok(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="ok")
    from luna_mcp.server import set_property
    result = await set_property("Player", "Rigidbody", "Mass", "5")
    assert result == "ok"
    mock_runtime.call.assert_called_once_with("setProperty", "Player", "Rigidbody", "Mass", 5)


async def test_set_property_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import set_property
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await set_property("Player", "Rigidbody", "Mass", "5")


# ── Phase 5: set_transform tool ──────────────────────────────────────────────

async def test_set_transform_returns_ok(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="ok")
    from luna_mcp.server import set_transform
    result = await set_transform("Player", "position", 1.0, 2.0, 3.0)
    assert result == "ok"
    mock_runtime.call.assert_called_once_with("setTransform", "Player", "position", 1.0, 2.0, 3.0)


async def test_set_transform_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import set_transform
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await set_transform("Player", "position", 0.0, 0.0, 0.0)


# ── Phase 6: find_objects tool ───────────────────────────────────────────────

async def test_find_objects_returns_paths(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="Player\nPlayer/Sword")
    from luna_mcp.server import find_objects
    result = await find_objects("Player")
    assert "Player" in result
    mock_runtime.call.assert_called_once_with("findObjects", "Player")


async def test_find_objects_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import find_objects
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await find_objects("Player")


# ── Phase 7: Debugger tools ──────────────────────────────────────────────────

@pytest.fixture
def mock_debugger(mock_bridge):
    from luna_mcp.debugger import Debugger
    dbg = Mock(spec=Debugger)
    dbg.set_breakpoint = AsyncMock(return_value="1:41:0:.*Player\\.js")
    dbg.remove_breakpoint = AsyncMock()
    dbg.pause = AsyncMock()
    dbg.resume = AsyncMock()
    dbg.get_call_stack = Mock(return_value="#0 PlayerUpdate (Player.js:11)")
    dbg.get_scope_variables = AsyncMock(return_value="speed: 4.2\nhealth: 100")
    server_module.debugger = dbg
    return dbg


async def test_set_breakpoint_returns_id(mock_debugger):
    from luna_mcp.server import set_breakpoint
    result = await set_breakpoint(".*Player\\.js", 42)
    assert "1:41:0:.*Player\\.js" in result
    mock_debugger.set_breakpoint.assert_called_once_with(".*Player\\.js", 42)


async def test_set_breakpoint_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import set_breakpoint
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await set_breakpoint(".*Player\\.js", 42)


async def test_remove_breakpoint_returns_ok(mock_debugger):
    from luna_mcp.server import remove_breakpoint
    result = await remove_breakpoint("1:41:0:.*Player\\.js")
    assert "1:41:0:.*Player\\.js" in result
    mock_debugger.remove_breakpoint.assert_called_once_with("1:41:0:.*Player\\.js")


async def test_debug_pause_returns_ok(mock_debugger):
    from luna_mcp.server import debug_pause
    result = await debug_pause()
    assert result == "Paused"
    mock_debugger.pause.assert_called_once()


async def test_debug_resume_returns_ok(mock_debugger):
    from luna_mcp.server import debug_resume
    result = await debug_resume()
    assert result == "Resumed"
    mock_debugger.resume.assert_called_once()


async def test_get_call_stack_returns_text(mock_debugger):
    from luna_mcp.server import get_call_stack
    result = await get_call_stack()
    assert "#0 PlayerUpdate" in result
    mock_debugger.get_call_stack.assert_called_once()


async def test_get_scope_variables_returns_text(mock_debugger):
    from luna_mcp.server import get_scope_variables
    result = await get_scope_variables(frame_index=0)
    assert "speed: 4.2" in result
    mock_debugger.get_scope_variables.assert_called_once_with(0)


async def test_get_call_stack_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_call_stack
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_call_stack()


async def test_get_scope_variables_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import get_scope_variables
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await get_scope_variables()


# ── Phase 8: batch tool ──────────────────────────────────────────────────────

async def test_batch_tool_executes_ping(mock_bridge):
    from luna_mcp.server import batch
    result = await batch("ping")
    assert "--- ping ---" in result
    assert "pong" in result


async def test_batch_tool_executes_multiple(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_bridge.eval = AsyncMock(return_value="pong")
    mock_runtime.call = AsyncMock(return_value="Root [Scene]")
    from luna_mcp.server import batch
    result = await batch("ping\nget_hierarchy depth=2")
    assert "--- ping ---" in result
    assert "--- get_hierarchy ---" in result
    assert "Root [Scene]" in result


async def test_batch_tool_stop_mode(mock_bridge):
    from luna_mcp.server import batch
    # unknown command triggers error; stop mode should not run subsequent commands
    result = await batch("nonexistent\nping", mode="stop")
    assert "error:" in result
    # ping should not appear since we stopped
    assert result.count("--- ping ---") == 0


# ── Phase 9: discover/register custom components ─────────────────────────────

async def test_discover_custom_components_calls_runtime(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="Inventory_V1: com.example.Inventory_V1")
    from luna_mcp.server import discover_custom_components
    result = await discover_custom_components()
    assert "Inventory_V1" in result
    mock_runtime.call.assert_called_once_with("discoverCustomComponents")


async def test_discover_custom_components_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import discover_custom_components
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await discover_custom_components()


async def test_register_custom_components_calls_runtime(mock_bridge, mock_runtime):
    server_module.runtime = mock_runtime
    mock_runtime.call = AsyncMock(return_value="registered 3 custom component(s)")
    from luna_mcp.server import register_custom_components
    result = await register_custom_components()
    assert "registered 3" in result
    mock_runtime.call.assert_called_once_with("registerCustomComponents")


async def test_register_custom_components_not_connected_raises():
    server_module.bridge = None
    from luna_mcp.server import register_custom_components
    with pytest.raises(ToolError, match="not (connected|initialized)"):
        await register_custom_components()
