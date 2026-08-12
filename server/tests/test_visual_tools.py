"""Phase 11: Visual Debugging Tools — TDD tests."""
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


# ── pause_game ───────────────────────────────────────────────────────────────

async def test_pause_game_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="paused (timeScale=0)")
    from luna_mcp.server import pause_game
    result = await pause_game()
    mock_runtime.call.assert_called_once_with("pauseGame")
    assert "paused" in result


async def test_pause_game_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import pause_game
    with pytest.raises(ToolError, match="not initialized"):
        await pause_game()


# ── resume_game ──────────────────────────────────────────────────────────────

async def test_resume_game_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="resumed (timeScale=1)")
    from luna_mcp.server import resume_game
    result = await resume_game()
    mock_runtime.call.assert_called_once_with("resumeGame")
    assert "resumed" in result


# ── get_game_state ───────────────────────────────────────────────────────────

async def test_get_game_state_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="timeScale: 1\npaused: false\neditorCamera: false")
    from luna_mcp.server import get_game_state
    result = await get_game_state()
    mock_runtime.call.assert_called_once_with("getGameState")
    assert "timeScale" in result


# ── get_layers ───────────────────────────────────────────────────────────────

async def test_get_layers_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="LAYERS:\n0: Default\n5: UI\n\nSORTING LAYERS:\n(none)")
    from luna_mcp.server import get_layers
    result = await get_layers()
    mock_runtime.call.assert_called_once_with("getLayers")
    assert "LAYERS:" in result


# ── diagnose_object ──────────────────────────────────────────────────────────

async def test_diagnose_object_calls_js_helper(mock_runtime, mock_bridge):
    mock_runtime.call = AsyncMock(return_value="DIAGNOSE: Player\n[OK] exists\n[OK] active (self + parents)")
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import diagnose_object
    result = await diagnose_object("Player")
    mock_runtime.call.assert_called_once_with("diagnoseObject", "Player")
    assert "DIAGNOSE: Player" in result


async def test_diagnose_object_appends_console_errors(mock_runtime, mock_bridge):
    mock_runtime.call = AsyncMock(return_value="DIAGNOSE: Player\n[OK] exists")
    mock_bridge.get_console_messages = Mock(return_value=[
        {"level": "E", "text": "NullRef at Player.Update:42", "timestamp": 0}
    ])
    from luna_mcp.server import diagnose_object
    result = await diagnose_object("Player")
    assert "[!!] console:" in result
    assert "NullRef" in result


async def test_diagnose_object_no_errors_appends_clean(mock_runtime, mock_bridge):
    mock_runtime.call = AsyncMock(return_value="DIAGNOSE: Player\n[OK] exists")
    mock_bridge.get_console_messages = Mock(return_value=[])
    from luna_mcp.server import diagnose_object
    result = await diagnose_object("Player")
    assert "[--] no console errors" in result


async def test_diagnose_object_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import diagnose_object
    with pytest.raises(ToolError, match="not initialized"):
        await diagnose_object("Player")


# ── get_materials ────────────────────────────────────────────────────────────

async def test_get_materials_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="MATERIALS: Player\n  MeshRenderer:\n    [0] Standard (Shader: Standard)")
    from luna_mcp.server import get_materials
    result = await get_materials("Player")
    mock_runtime.call.assert_called_once_with("getMaterials", "Player", False)
    assert "MATERIALS:" in result


async def test_get_materials_with_children(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="MATERIALS: Player\n  ...")
    from luna_mcp.server import get_materials
    await get_materials("Player", include_children=True)
    mock_runtime.call.assert_called_once_with("getMaterials", "Player", True)


# ── get_animator_state ────────────────────────────────────────────────────────

async def test_get_animator_state_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="ANIMATOR: Player\n  layer[0]: Base Layer (weight=1)")
    from luna_mcp.server import get_animator_state
    result = await get_animator_state("Player")
    mock_runtime.call.assert_called_once_with("getAnimatorState", "Player")
    assert "ANIMATOR:" in result


async def test_get_animator_state_no_debugger_returns_error(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: requires Luna Debugger extension")
    from luna_mcp.server import get_animator_state
    result = await get_animator_state("Player")
    assert "error" in result.lower()


# ── set_animator_param ────────────────────────────────────────────────────────

async def test_set_animator_param_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="ok: parameters/Speed = 5.0")
    from luna_mcp.server import set_animator_param
    result = await set_animator_param("Player", "Speed", "5.0")
    # value should be parsed (5.0 float), is_trigger=False
    mock_runtime.call.assert_called_once_with("setAnimatorParam", "Player", "Speed", 5.0, False)
    assert "ok" in result


async def test_set_animator_param_trigger(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="ok: triggers/Jump = true")
    from luna_mcp.server import set_animator_param
    await set_animator_param("Player", "Jump", "true", is_trigger=True)
    mock_runtime.call.assert_called_once_with("setAnimatorParam", "Player", "Jump", True, True)


# ── toggle_editor_camera ──────────────────────────────────────────────────────

async def test_toggle_editor_camera_enable(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="editor camera ON (WASD=move, right-click+drag=look, Q/E=up/down, scroll=zoom)")
    from luna_mcp.server import toggle_editor_camera
    result = await toggle_editor_camera(enable=True)
    mock_runtime.call.assert_called_once_with("toggleEditorCamera", True)
    assert "editor camera" in result


async def test_toggle_editor_camera_toggle(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="editor camera OFF (game cameras restored)")
    from luna_mcp.server import toggle_editor_camera
    await toggle_editor_camera()
    mock_runtime.call.assert_called_once_with("toggleEditorCamera")


# ── show_collider ─────────────────────────────────────────────────────────────

async def test_show_collider_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="showing collider: BoxCollider on Player")
    from luna_mcp.server import show_collider
    result = await show_collider("Player")
    mock_runtime.call.assert_called_once_with("showCollider", "Player")
    assert "collider" in result


async def test_show_collider_no_debugger_returns_error(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: requires Luna Debugger extension")
    from luna_mcp.server import show_collider
    result = await show_collider("Player")
    assert "error" in result.lower()


# ── hide_collider ─────────────────────────────────────────────────────────────

async def test_hide_collider_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="collider hidden")
    from luna_mcp.server import hide_collider
    result = await hide_collider()
    mock_runtime.call.assert_called_once_with("hideCollider")
    assert "collider" in result


async def test_hide_collider_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import hide_collider
    with pytest.raises(ToolError, match="not initialized"):
        await hide_collider()


# ── set_field ─────────────────────────────────────────────────────────────────

async def test_set_field_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="ok: Player/BoxCollider/mass = 5.0")
    from luna_mcp.server import set_field
    result = await set_field("Player", "BoxCollider", "mass", "5.0", "number")
    mock_runtime.call.assert_called_once_with("setField", "Player", "BoxCollider", "mass", "5.0", "number")
    assert "ok" in result


async def test_set_field_no_debugger_returns_error(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: requires Luna Debugger extension")
    from luna_mcp.server import set_field
    result = await set_field("Player", "BoxCollider", "mass", "5.0", "number")
    assert "error" in result.lower()


# ── toggle_profiler ───────────────────────────────────────────────────────────

async def test_toggle_profiler_enable(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="profiler ON (FPS/ms/memory overlay)")
    from luna_mcp.server import toggle_profiler
    result = await toggle_profiler(enable=True)
    mock_runtime.call.assert_called_once_with("toggleProfiler", True)
    assert "profiler ON" in result


async def test_toggle_profiler_toggle(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="profiler OFF")
    from luna_mcp.server import toggle_profiler
    await toggle_profiler()
    mock_runtime.call.assert_called_once_with("toggleProfiler")


async def test_toggle_profiler_no_debugger_returns_error(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: requires Luna Debugger extension")
    from luna_mcp.server import toggle_profiler
    result = await toggle_profiler()
    assert "error" in result.lower()


# ── show_collider_overlay ─────────────────────────────────────────────────────

async def test_show_collider_overlay_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="showing 2 colliders on Player")
    from luna_mcp.server import show_collider_overlay
    result = await show_collider_overlay("Player")
    mock_runtime.call.assert_called_once_with("showColliderOverlay", "Player")
    assert "collider" in result


async def test_show_collider_overlay_not_found(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: node not found: NonExistent")
    from luna_mcp.server import show_collider_overlay
    result = await show_collider_overlay("NonExistent")
    assert "error" in result


async def test_show_collider_overlay_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import show_collider_overlay
    with pytest.raises(ToolError, match="not initialized"):
        await show_collider_overlay("Player")


# ── show_all_collider_overlays ────────────────────────────────────────────────

async def test_show_all_collider_overlays_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="showing 5 collider overlays (green=box, blue=sphere, yellow=capsule)")
    from luna_mcp.server import show_all_collider_overlays
    result = await show_all_collider_overlays()
    mock_runtime.call.assert_called_once_with("showAllColliderOverlays", 20, True)
    assert "collider" in result


async def test_show_all_collider_overlays_max_count_capped(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="showing 50 collider overlays (green=box, blue=sphere, yellow=capsule)")
    from luna_mcp.server import show_all_collider_overlays
    await show_all_collider_overlays(max_count=999)
    mock_runtime.call.assert_called_once_with("showAllColliderOverlays", 50, True)


async def test_show_all_collider_overlays_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import show_all_collider_overlays
    with pytest.raises(ToolError, match="not initialized"):
        await show_all_collider_overlays()


# ── hide_collider_overlays ────────────────────────────────────────────────────

async def test_hide_collider_overlays_calls_js_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="removed 3 collider overlays")
    from luna_mcp.server import hide_collider_overlays
    result = await hide_collider_overlays()
    mock_runtime.call.assert_called_once_with("hideColliderOverlays")
    assert "removed" in result


async def test_hide_collider_overlays_none_present(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="removed 0 collider overlays")
    from luna_mcp.server import hide_collider_overlays
    result = await hide_collider_overlays()
    assert "0" in result


async def test_hide_collider_overlays_not_initialized():
    server_module.bridge = None
    from luna_mcp.server import hide_collider_overlays
    with pytest.raises(ToolError, match="not initialized"):
        await hide_collider_overlays()


# ── visual_summary ────────────────────────────────────────────────────────────

async def test_visual_summary_compact_format(mock_runtime):
    canned = "Scene 800x1280 @60fps | 7 vis\nbg: full | hero: C 45%h [Idle loop t=.32] | logo: TR 12%h\nbtn 'INSTALL': B 30%h [pulse scale=1.05]\nno end-card | 0 errors"
    mock_runtime.call = AsyncMock(return_value=canned)
    from luna_mcp.server import visual_summary
    result = await visual_summary("compact")
    mock_runtime.call.assert_called_once_with("visualSummary", "compact")
    assert "Scene" in result
    assert "vis" in result
    assert "end-card" in result


async def test_visual_summary_no_camera(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="no main camera")
    from luna_mcp.server import visual_summary
    result = await visual_summary("compact")
    assert result == "no main camera"


async def test_visual_diff_endcard_appeared(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="DIFF vs t-2.4s:\n+ EndCard/Panel: full screen [fadeIn t=.7]\nend-card: NO -> YES")
    from luna_mcp.server import visual_diff
    result = await visual_diff()
    mock_runtime.call.assert_called_once_with("visualDiff", "")
    assert "+ EndCard" in result


async def test_token_budget(mock_runtime):
    canned = "Scene 800x1280 @60fps | 7 vis\nbg: full | hero: C 45%h [Idle] | logo: TR 12%h\nbtn 'INSTALL': B 30%h | particles: T 25%h\nno end-card | 0 errors"
    mock_runtime.call = AsyncMock(return_value=canned)
    from luna_mcp.server import visual_summary
    result = await visual_summary("compact")
    assert len(result) < 1200


async def test_visual_diff_empty_prev(mock_runtime):
    snap = "Scene 800x1280 @60fps | 3 vis\nbg: full\nno end-card | 0 errors"
    mock_runtime.call = AsyncMock(return_value="no prev: " + snap)
    from luna_mcp.server import visual_diff
    result = await visual_diff()
    assert result.startswith("no prev:")
