"""Phase 14: Engine tools -- render stats, VRAM, GPU, step frame, toggle active, move camera. TDD."""
from unittest.mock import AsyncMock, Mock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import luna_mcp.server as server_module


@pytest.fixture(autouse=True)
def reset_bridge():
    orig_bridge = server_module.bridge
    orig_runtime = server_module.runtime
    yield
    server_module.bridge = orig_bridge
    server_module.runtime = orig_runtime


@pytest.fixture
def mock_runtime(reset_bridge):
    bridge = Mock()
    bridge.connected = True
    bridge.eval = AsyncMock(return_value="ok")
    server_module.bridge = bridge
    runtime = Mock()
    runtime.call = AsyncMock(return_value="ok")
    server_module.runtime = runtime
    return runtime


# ── get_render_stats ──────────────────────────────────────────────────────────

async def test_get_render_stats_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="FPS: 60\ntriangles: 1234\ndraw calls: 45")
    from luna_mcp.server import get_render_stats
    result = await get_render_stats()
    mock_runtime.call.assert_called_once_with("getRenderStats")
    assert "FPS" in result
    assert "triangles" in result


async def test_get_render_stats_not_connected():
    server_module.bridge = None
    from luna_mcp.server import get_render_stats
    with pytest.raises(ToolError):
        await get_render_stats()


# ── get_vram_usage ────────────────────────────────────────────────────────────

async def test_get_vram_usage_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="VRAM total: 32.5MB\n  textures: 28.0MB\n  vertex buffers: 4.5MB")
    from luna_mcp.server import get_vram_usage
    result = await get_vram_usage()
    mock_runtime.call.assert_called_once_with("getVramUsage")
    assert "VRAM" in result
    assert "textures" in result


async def test_get_vram_usage_not_connected():
    server_module.bridge = None
    from luna_mcp.server import get_vram_usage
    with pytest.raises(ToolError):
        await get_vram_usage()


# ── get_gpu_info ──────────────────────────────────────────────────────────────

async def test_get_gpu_info_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="WebGL: 2.0\nvendor: Google Inc.\nrenderer: ANGLE\nmax texture: 16384")
    from luna_mcp.server import get_gpu_info
    result = await get_gpu_info()
    mock_runtime.call.assert_called_once_with("getGpuInfo")
    assert "WebGL" in result
    assert "max texture" in result


async def test_get_gpu_info_not_connected():
    server_module.bridge = None
    from luna_mcp.server import get_gpu_info
    with pytest.raises(ToolError):
        await get_gpu_info()


# ── step_frame ────────────────────────────────────────────────────────────────

async def test_step_frame_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="stepped 1 frame (frame 42)")
    from luna_mcp.server import step_frame
    result = await step_frame()
    mock_runtime.call.assert_called_once_with("stepFrame")
    assert "stepped" in result


async def test_step_frame_not_connected():
    server_module.bridge = None
    from luna_mcp.server import step_frame
    with pytest.raises(ToolError):
        await step_frame()


# ── toggle_active ─────────────────────────────────────────────────────────────

async def test_toggle_active_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="deactivated: Player")
    from luna_mcp.server import toggle_active
    result = await toggle_active("Player")
    mock_runtime.call.assert_called_once_with("toggleActive", "Player")
    assert "Player" in result


async def test_toggle_active_not_found(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: not found: Ghost")
    from luna_mcp.server import toggle_active
    result = await toggle_active("Ghost")
    assert "error" in result


async def test_toggle_active_not_connected():
    server_module.bridge = None
    from luna_mcp.server import toggle_active
    with pytest.raises(ToolError):
        await toggle_active("Player")


# ── move_camera ───────────────────────────────────────────────────────────────

async def test_move_camera_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="camera moved to (1.0, 2.0, 3.0)")
    from luna_mcp.server import move_camera
    result = await move_camera(1.0, 2.0, 3.0)
    mock_runtime.call.assert_called_once_with("moveCamera", 1.0, 2.0, 3.0)
    assert "camera moved" in result


async def test_move_camera_no_camera(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="error: no camera found")
    from luna_mcp.server import move_camera
    result = await move_camera(0, 0, 0)
    assert "error" in result


async def test_move_camera_not_connected():
    server_module.bridge = None
    from luna_mcp.server import move_camera
    with pytest.raises(ToolError):
        await move_camera(0, 0, 0)


# ── batch registration ────────────────────────────────────────────────────────

async def test_engine_tools_registered_for_batch(mock_runtime):
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    for name in ("get_render_stats", "get_vram_usage", "get_gpu_info",
                 "step_frame", "toggle_active", "move_camera"):
        assert name in _TOOL_REGISTRY, f"{name} not in batch registry"
