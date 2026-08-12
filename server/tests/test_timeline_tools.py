"""TDD tests for timeline_tools: capture_timeline, analyze_animation,
compare_animation_states, motion_summary."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_tools(bridge=None, sampling=None):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.timeline import _LabelCache
    from luna_mcp.tools.timeline_tools import register_timeline_tools
    mcp = FastMCP("test")
    cache = _LabelCache()
    tools = register_timeline_tools(
        mcp,
        get_bridge=lambda: bridge,
        get_sampling=lambda: sampling,
        get_cache=lambda: cache,
        exposed=set(),
    )
    return tools, cache


def _make_bridge(eval_result="ok"):
    bridge = MagicMock()
    bridge.screenshot = AsyncMock(return_value=b"\x89PNG")
    bridge.eval = AsyncMock(return_value=eval_result)
    return bridge


def _make_sampling(result="verdict text"):
    svc = MagicMock()
    svc.enabled = True
    svc.describe_image_multi = AsyncMock(return_value=result)
    return svc


# ── capture_timeline ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capture_timeline_returns_paths(tmp_path):
    """Returns newline-joined t=Xms /path lines."""
    bridge = _make_bridge()
    tools, _ = _make_tools(bridge=bridge)
    fn = tools["capture_timeline"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        result = await fn(duration_ms=500, fps=2)

    lines = result.strip().split("\n")
    assert len(lines) == 2
    assert all(line.startswith("t=") for line in lines)
    assert all("ms " in line for line in lines)


@pytest.mark.asyncio
async def test_capture_timeline_invalid_fps_returns_error(tmp_path):
    """fps > 8 returns [INVALID: ...] string."""
    bridge = _make_bridge()
    tools, _ = _make_tools(bridge=bridge)
    fn = tools["capture_timeline"][0]

    result = await fn(duration_ms=500, fps=10)
    assert "[INVALID" in result


# ── motion_summary ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_motion_summary_calls_js_helper():
    """Calls bridge.eval with sampleMotionTimeline JS."""
    timeline_data = "t=0.10 p=(0.0,1.0) nt=0.25 pc=-\nt=0.20 p=(0.0,2.0) nt=0.50 pc=-\nSUMMARY: dY=1.0"
    bridge = _make_bridge(eval_result=timeline_data)
    tools, _ = _make_tools(bridge=bridge)
    fn = tools["motion_summary"][0]

    result = await fn(path="Hero/Body", duration_ms=200, samples=2)

    assert bridge.eval.called
    call_expr = bridge.eval.call_args[0][0]
    assert "sampleMotionTimeline" in call_expr
    assert "Hero/Body" in call_expr
    assert "TIMELINE:" in result


@pytest.mark.asyncio
async def test_motion_summary_no_data_returns_placeholder():
    """Empty eval result returns '[no data]'."""
    bridge = _make_bridge(eval_result="")
    tools, _ = _make_tools(bridge=bridge)
    fn = tools["motion_summary"][0]

    result = await fn(path="X", duration_ms=100, samples=2)
    assert "[no data]" in result


# ── analyze_animation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_animation_falls_back_when_sampling_disabled(tmp_path):
    """Falls back to motion_summary when sampling.enabled=False."""
    disabled_sampling = MagicMock()
    disabled_sampling.enabled = False
    timeline_data = "t=0.10 p=(0.0,1.0) nt=0.25 pc=-\nSUMMARY: dY=0.0"
    bridge = _make_bridge(eval_result=timeline_data)
    tools, _ = _make_tools(bridge=bridge, sampling=disabled_sampling)
    fn = tools["analyze_animation"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        result = await fn(target_path="Hero", focus="motion", duration_ms=200, fps=2)

    assert "TIMELINE:" in result
    disabled_sampling.describe_image_multi.assert_not_called() if hasattr(disabled_sampling.describe_image_multi, "assert_not_called") else None


@pytest.mark.asyncio
async def test_analyze_animation_calls_describe_multi(tmp_path):
    """With sampling enabled, calls describe_image_multi with all frame paths."""
    sampling = _make_sampling("bouncing smoothly")
    bridge = _make_bridge()
    tools, _ = _make_tools(bridge=bridge, sampling=sampling)
    fn = tools["analyze_animation"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        result = await fn(target_path="Hero", focus="motion", duration_ms=500, fps=2)

    assert "VERDICT: bouncing smoothly" in result
    sampling.describe_image_multi.assert_called_once()
    call_args = sampling.describe_image_multi.call_args
    paths_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("image_paths", [])
    assert len(paths_arg) == 2


# ── compare_animation_states ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_states_first_call_captures_label_a(tmp_path):
    """First call captures frames and stores as label_a, returns CAPTURED message."""
    bridge = _make_bridge()
    tools, cache = _make_tools(bridge=bridge)
    fn = tools["compare_animation_states"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        result = await fn(label_a="before", label_b="after", duration_ms=200, fps=2)

    assert "CAPTURED" in result
    assert "before" in result
    assert cache.get("before") is not None


@pytest.mark.asyncio
async def test_compare_states_second_call_diffs(tmp_path):
    """Second call (label_a cached) captures label_b and calls describe_image_multi."""
    sampling = _make_sampling("animation changed: faster")
    bridge = _make_bridge()
    tools, cache = _make_tools(bridge=bridge, sampling=sampling)
    fn = tools["compare_animation_states"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        # First call — capture label_a
        await fn(label_a="before", label_b="after", duration_ms=200, fps=2)
        # Second call — diff
        result = await fn(label_a="before", label_b="after", duration_ms=200, fps=2)

    assert "DIFF" in result
    assert "before" in result
    assert "after" in result
    sampling.describe_image_multi.assert_called_once()


@pytest.mark.asyncio
async def test_compare_states_label_a_evicted_from_cache_recaptures(tmp_path):
    """If label_a is evicted, next call re-captures it (returns CAPTURED again)."""
    bridge = _make_bridge()
    tools, cache = _make_tools(bridge=bridge)
    fn = tools["compare_animation_states"][0]

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        # Manually prime with an expired/missing label_a
        result = await fn(label_a="gone", label_b="new", duration_ms=200, fps=2)

    # label_a missing → re-captures
    assert "CAPTURED" in result
