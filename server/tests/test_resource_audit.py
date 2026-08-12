"""Resource Usage Audit Tools -- TDD tests."""
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


# ── audit_build_size ─────────────────────────────────────────────────────────

async def test_audit_build_size_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="BUILD SIZE: 16.5MB total\nSCRIPTS (15.7MB):\n[!!] UnityScriptsCompiler.js  4853KB"
    )
    from luna_mcp.server import audit_build_size
    result = await audit_build_size()
    mock_runtime.call.assert_called_once_with("auditBuildSize")
    assert "BUILD SIZE" in result
    assert "SCRIPTS" in result


async def test_audit_build_size_not_connected():
    server_module.bridge = None
    from luna_mcp.server import audit_build_size
    with pytest.raises(ToolError):
        await audit_build_size()


async def test_audit_build_size_shows_categories(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="BUILD SIZE: 2.0MB total\nSCRIPTS (1.5MB):\n[OK] main.js  1500KB\nIMAGES (500KB, 5 files)\nAUDIO (0KB, 0 files)"
    )
    from luna_mcp.server import audit_build_size
    result = await audit_build_size()
    assert "IMAGES" in result
    assert "AUDIO" in result


# ── audit_unused_modules ─────────────────────────────────────────────────────

async def test_audit_unused_modules_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="MODULE USAGE ANALYSIS:\n[!!] TextMeshPro.js (2341KB) — NO TMP components found. REMOVE to save 2.3MB"
    )
    from luna_mcp.server import audit_unused_modules
    result = await audit_unused_modules()
    mock_runtime.call.assert_called_once_with("auditUnusedModules")
    assert "MODULE USAGE" in result


async def test_audit_unused_modules_not_connected():
    server_module.bridge = None
    from luna_mcp.server import audit_unused_modules
    with pytest.raises(ToolError):
        await audit_unused_modules()


async def test_audit_unused_modules_shows_savings(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="MODULE USAGE ANALYSIS:\n[!!] physics2d-0.js (443KB) — NO 2D physics\n\nPOTENTIAL SAVINGS: 443KB (3% of build)"
    )
    from luna_mcp.server import audit_unused_modules
    result = await audit_unused_modules()
    assert "POTENTIAL SAVINGS" in result


# ── audit_unused_assets ──────────────────────────────────────────────────────

async def test_audit_unused_assets_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="UNUSED ASSETS:\n[!!] bg_unused.png (120KB) — not referenced by any renderer\nUSED: 58 textures, 8 audio clips"
    )
    from luna_mcp.server import audit_unused_assets
    result = await audit_unused_assets()
    mock_runtime.call.assert_called_once_with("auditUnusedAssets")
    assert "UNUSED ASSETS" in result


async def test_audit_unused_assets_not_connected():
    server_module.bridge = None
    from luna_mcp.server import audit_unused_assets
    with pytest.raises(ToolError):
        await audit_unused_assets()


async def test_audit_unused_assets_all_used(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="UNUSED ASSETS:\n(none detected)\nUSED: 12 textures, 3 audio clips, 1 font"
    )
    from luna_mcp.server import audit_unused_assets
    result = await audit_unused_assets()
    assert "none detected" in result


# ── get_build_recommendations ─────────────────────────────────────────────────

async def test_get_build_recommendations_calls_helper(mock_runtime):
    mock_runtime.call = AsyncMock(
        return_value="BUILD OPTIMIZATION RECOMMENDATIONS:\n1. [CRITICAL] Remove TextMeshPro — saves 2.3MB"
    )
    from luna_mcp.server import get_build_recommendations
    result = await get_build_recommendations()
    mock_runtime.call.assert_called_once_with("getBuildRecommendations")
    assert "BUILD OPTIMIZATION" in result


async def test_get_build_recommendations_not_connected():
    server_module.bridge = None
    from luna_mcp.server import get_build_recommendations
    with pytest.raises(ToolError):
        await get_build_recommendations()


# ── batch registration ────────────────────────────────────────────────────────

async def test_audit_tools_registered_for_batch(mock_runtime):
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    assert "audit_build_size" in _TOOL_REGISTRY
    assert "audit_unused_modules" in _TOOL_REGISTRY
    assert "audit_unused_assets" in _TOOL_REGISTRY
    assert "get_build_recommendations" in _TOOL_REGISTRY
