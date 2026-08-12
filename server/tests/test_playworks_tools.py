"""Phase 13: Playworks Performance & Diagnostics Tools -- TDD tests."""
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


# ── get_performance_metrics ─────────────────────────────────────────────────

async def test_get_performance_metrics_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="PERFORMANCE:\nfps: 42 (GOOD)")
    from luna_mcp.server import get_performance_metrics
    result = await get_performance_metrics()
    mock_runtime.call.assert_called_once_with("getPerformanceMetrics")
    assert "fps:" in result
    assert "PERFORMANCE" in result


async def test_get_performance_metrics_not_connected():
    server_module.bridge = None
    from luna_mcp.server import get_performance_metrics
    with pytest.raises(ToolError):
        await get_performance_metrics()


# ── diagnose_rendering ──────────────────────────────────────────────────────

async def test_diagnose_rendering_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="RENDERING DIAGNOSTICS:\nwebgl: 2.0\nshaders: 14")
    from luna_mcp.server import diagnose_rendering
    result = await diagnose_rendering()
    mock_runtime.call.assert_called_once_with("diagnoseRendering")
    assert "webgl:" in result
    assert "shaders:" in result


async def test_diagnose_rendering_not_connected():
    server_module.bridge = None
    from luna_mcp.server import diagnose_rendering
    with pytest.raises(ToolError):
        await diagnose_rendering()


async def test_diagnose_rendering_passes_through_lightcount(mock_runtime):
    """S5.5: diagnose_rendering passes lightCount field through unchanged."""
    mock_runtime.call = AsyncMock(
        return_value="RENDERING DIAGNOSTICS:\nwebgl: 2.0\nlightCount: 3"
    )
    from luna_mcp.server import diagnose_rendering
    result = await diagnose_rendering()
    assert "lightCount:" in result


# ── audit_textures ──────────────────────────────────────────────────────────

async def test_audit_textures_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="TEXTURES (3):\n2048x2048 16384KB bg fmt:5 [!!]\n---\ntotal: 16.0MB est.\noversized (>1024): 1 [!!]"
    )
    from luna_mcp.server import audit_textures
    result = await audit_textures()
    mock_runtime.call.assert_called_once_with("auditTextures")
    assert "TEXTURES" in result
    assert "oversized" in result


async def test_audit_textures_empty_scene(mock_runtime):
    mock_runtime.call = AsyncMock(return_value="no textures found (renderers may use procedural materials)")
    from luna_mcp.server import audit_textures
    result = await audit_textures()
    assert "no textures" in result


async def test_audit_textures_not_connected():
    server_module.bridge = None
    from luna_mcp.server import audit_textures
    with pytest.raises(ToolError):
        await audit_textures()


# ── batch integration ───────────────────────────────────────────────────────

async def test_tools_registered_for_batch(mock_runtime):
    """All 3 tools should be available in batch commands."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    assert "get_performance_metrics" in _TOOL_REGISTRY
    assert "diagnose_rendering" in _TOOL_REGISTRY
    assert "audit_textures" in _TOOL_REGISTRY
