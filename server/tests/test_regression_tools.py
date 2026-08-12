"""TDD tests for regression/tools.py — 4 MCP tools."""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image


def _make_png_bytes(color=(200, 100, 50), size=(50, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_bridge():
    b = MagicMock()
    b.eval = AsyncMock(return_value="build-test-001")
    b.screenshot = AsyncMock(return_value=_make_png_bytes())
    return b


@pytest.fixture
def mock_store(tmp_path):
    from luna_mcp.regression.store import BaselineStore
    return BaselineStore(root=tmp_path / "baselines")


@pytest.fixture
def sampling_disabled():
    s = MagicMock()
    s.enabled = False
    return s


@pytest.fixture
def sampling_enabled():
    s = MagicMock()
    s.enabled = True
    s.verify_visual_diff = AsyncMock(return_value="PASS looks identical")
    return s


# ── helper: make tools instance ──────────────────────────────────────────────

def _make_tools(bridge, store, sampling=None):
    from luna_mcp.regression.tools import RegressionTools
    if sampling is None:
        sampling = MagicMock()
        sampling.enabled = False
    return RegressionTools(bridge=bridge, store=store, sampling=sampling)


# 1
async def test_baseline_save_calls_screenshot_and_store(mock_bridge, mock_store, sampling_disabled):
    tools = _make_tools(mock_bridge, mock_store, sampling_disabled)
    result = await tools.visual_baseline_save("main")
    mock_bridge.screenshot.assert_called_once()
    assert "saved" in result.lower()
    # verify baseline was actually persisted
    build_dirs = list(mock_store.root.iterdir())
    assert build_dirs, "no build directory created"
    saved_names = mock_store.list(build_dirs[0].name)
    assert "main" in saved_names, f"baseline not saved: {saved_names}"


# 2
async def test_baseline_check_pass_under_threshold(mock_bridge, mock_store):
    """Pixel diff < threshold → PASS."""
    # Save baseline first
    png = _make_png_bytes()
    tools = _make_tools(mock_bridge, mock_store)
    # Override bridge to return same png on both save and check
    mock_bridge.screenshot = AsyncMock(return_value=png)
    mock_bridge.eval = AsyncMock(return_value="build123")
    await tools.visual_baseline_save("main")
    result = await tools.visual_baseline_check("main")
    assert result.startswith("PASS")


# 3
async def test_baseline_check_fails_high_pct(mock_bridge, mock_store, sampling_disabled):
    """Diff > threshold → DIFF reported."""
    tools = _make_tools(mock_bridge, mock_store, sampling_disabled)
    mock_bridge.eval = AsyncMock(return_value="build123")
    # Save with one color
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes(color=(0, 0, 255)))
    await tools.visual_baseline_save("main", pixel_threshold=1.0)
    # Check with completely different color
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes(color=(255, 0, 0)))
    result = await tools.visual_baseline_check("main")
    assert result.startswith("DIFF")
    assert "pct=" in result


# 4
async def test_baseline_check_semantic_when_sampling_enabled(mock_bridge, mock_store, sampling_enabled):
    """When diff > threshold and sampling enabled → calls verify_visual_diff."""
    tools = _make_tools(mock_bridge, mock_store, sampling_enabled)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes(color=(0, 0, 255)))
    await tools.visual_baseline_save("main", pixel_threshold=1.0)
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes(color=(255, 0, 0)))
    result = await tools.visual_baseline_check("main")
    sampling_enabled.verify_visual_diff.assert_called_once()
    assert "semantic" in result


# 5
async def test_baseline_check_no_baseline_returns_invalid(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    result = await tools.visual_baseline_check("nonexistent")
    assert "[INVALID" in result
    assert "not found" in result


# 6
async def test_baseline_list_for_current_build(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("main")
    await tools.visual_baseline_save("endcard")
    result = await tools.visual_baseline_list()
    assert "main" in result
    assert "endcard" in result


# 7
async def test_baseline_invalidate_one(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("main")
    await tools.visual_baseline_save("endcard")
    result = await tools.visual_baseline_invalidate(name="main")
    assert "deleted" in result.lower() or "invalidat" in result.lower()
    listed = await tools.visual_baseline_list()
    assert "main" not in listed
    assert "endcard" in listed


# 8
async def test_baseline_invalidate_all(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("main")
    await tools.visual_baseline_save("endcard")
    result = await tools.visual_baseline_invalidate()
    listed = await tools.visual_baseline_list()
    assert listed.strip() == "" or "(none)" in listed


# 9
async def test_invalid_name_rejected(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    result = await tools.visual_baseline_save("INVALID NAME!")
    assert "[INVALID" in result


# 10
async def test_determinism_called_before_capture(mock_bridge, mock_store):
    """prepare_deterministic must be called before screenshot on check."""
    import luna_mcp.regression.tools as tools_mod
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("main")

    call_log = []

    async def tracked_prepare(*args, **kwargs):
        call_log.append("prepare")

    mock_bridge.screenshot = AsyncMock(
        side_effect=lambda: call_log.append("screenshot") or _make_png_bytes()
    )

    with patch.object(tools_mod._determinism_mod, "prepare_deterministic", side_effect=tracked_prepare):
        await tools.visual_baseline_check("main")

    assert "prepare" in call_log
    assert call_log.index("prepare") < call_log.index("screenshot")


async def test_baseline_save_passes_mask_zones(mock_bridge, mock_store):
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build123")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("main", mask_zones="0,0,10,10")
    bh = list(mock_store.root.iterdir())[0].name
    _, meta = mock_store.load(bh, "main")
    assert meta["mask_zones"] == "0,0,10,10"


async def test_baseline_save_with_build_hash_override(mock_bridge, mock_store):
    """visual_baseline_list(build_hash=...) uses provided hash."""
    tools = _make_tools(mock_bridge, mock_store)
    mock_bridge.eval = AsyncMock(return_value="build_X")
    mock_bridge.screenshot = AsyncMock(return_value=_make_png_bytes())
    await tools.visual_baseline_save("shot1")
    build_hash = list(mock_store.root.iterdir())[0].name
    result = await tools.visual_baseline_list(build_hash=build_hash)
    assert "shot1" in result
