from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def call_fn():
    return AsyncMock(return_value="result")


@pytest.fixture
def tools(call_fn):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.analysis_tools import register_analysis_tools
    mcp = FastMCP("test")
    return register_analysis_tools(mcp, call_fn), call_fn


# raycast
async def test_raycast_hit(tools):
    reg, call_fn = tools
    call_fn.return_value = "Scene/Player"
    fn, _ = reg["raycast"]
    result = await fn(100, 200)
    assert result == "Scene/Player"
    call_fn.assert_awaited_with("raycast", 100, 200)


async def test_raycast_no_hit(tools):
    reg, call_fn = tools
    call_fn.return_value = "no hit"
    fn, _ = reg["raycast"]
    result = await fn(0, 0)
    assert result == "no hit"


async def test_raycast_no_camera(tools):
    reg, call_fn = tools
    call_fn.return_value = "no camera"
    fn, _ = reg["raycast"]
    result = await fn(0, 0)
    assert result == "no camera"


# get_canvas_info
async def test_get_canvas_info_passes_path(tools):
    reg, call_fn = tools
    call_fn.return_value = "anchoredPosition: (0, 0)\nsizeDelta: (100, 50)"
    fn, _ = reg["get_canvas_info"]
    result = await fn("UI/Button")
    assert "anchoredPosition" in result
    call_fn.assert_awaited_with("getCanvasInfo", "UI/Button")


# compare_objects
async def test_compare_objects_passes_both_paths(tools):
    reg, call_fn = tools
    call_fn.return_value = "--- Transform ---\nposition: (1,2,3) vs (4,5,6)"
    fn, _ = reg["compare_objects"]
    result = await fn("A/Obj1", "B/Obj2")
    assert "vs" in result
    call_fn.assert_awaited_with("compareObjects", "A/Obj1", "B/Obj2")


# get_audio_sources
async def test_get_audio_sources_multi_line(tools):
    reg, call_fn = tools
    call_fn.return_value = "Scene/BGMusic: clip=bgm playing=true vol=0.8 loop=true\nScene/SFX: clip=click playing=false vol=1.0 loop=false"
    fn, _ = reg["get_audio_sources"]
    result = await fn()
    assert "BGMusic" in result
    call_fn.assert_awaited_with("getAudioSources")


async def test_get_audio_sources_empty(tools):
    reg, call_fn = tools
    call_fn.return_value = "(no AudioSource found)"
    fn, _ = reg["get_audio_sources"]
    result = await fn()
    assert "no AudioSource" in result


# get_physics_settings
async def test_get_physics_settings_returns_gravity(tools):
    reg, call_fn = tools
    call_fn.return_value = "gravity: (0, -9.81, 0)\nfixedDeltaTime: 0.02"
    fn, _ = reg["get_physics_settings"]
    result = await fn()
    assert "gravity" in result
    call_fn.assert_awaited_with("getPhysicsSettings")


async def test_get_physics_settings_error(tools):
    reg, call_fn = tools
    from mcp.server.fastmcp.exceptions import ToolError
    call_fn.side_effect = ToolError("no Physics module")
    fn, _ = reg["get_physics_settings"]
    with pytest.raises(ToolError):
        await fn()
