"""TDD tests for Cost Budget + Adaptive Routing (feature #6)."""
import os
from unittest.mock import AsyncMock, patch

import pytest

# ── Registry ──────────────────────────────────────────────────────────────────

def test_registry_lookup_known():
    from luna_mcp.budget.registry import TOOL_COSTS, ToolCost
    c = TOOL_COSTS["ping"]
    assert isinstance(c, ToolCost)
    assert c.tier == "trivial"
    assert c.est_in > 0
    assert c.est_out > 0


def test_registry_lookup_unknown():
    from luna_mcp.budget.registry import DEFAULT, cost_of
    c = cost_of("nonexistent_tool_xyz", {})
    assert c == DEFAULT


def test_cost_of_get_hierarchy_depth_aware():
    from luna_mcp.budget.registry import cost_of
    shallow = cost_of("get_hierarchy", {"depth": "2"})
    deep = cost_of("get_hierarchy", {"depth": "4"})
    assert shallow.est_out < deep.est_out
    assert shallow.tier == "cheap"
    assert deep.est_out == 5000


def test_cost_of_eval_js_dump_heuristic():
    from luna_mcp.budget.registry import cost_of
    normal = cost_of("eval_js", {"expression": "1+1"})
    dump_expr = cost_of("eval_js", {"expression": "JSON.stringify(scene)"})
    assert dump_expr.est_out > normal.est_out
    assert dump_expr.tier == "expensive"


# ── Tracker ───────────────────────────────────────────────────────────────────

def test_tracker_record_pct_remaining():
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10_000)
    assert t.remaining() == 10_000
    assert t.pct() == 0.0
    t.record("some_tool", 2_000)
    assert t.remaining() == 8_000
    assert t.pct() == pytest.approx(0.2)


def test_tracker_skip_downgrade_counters():
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10_000)
    t.record_skip("screenshot")
    t.record_skip("screenshot")
    t.record_downgrade("screenshot")
    assert t.skipped["screenshot"] == 2
    assert t.downgraded["screenshot"] == 1


def test_tracker_status_text():
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10_000)
    t.record("ping", 500)
    s = t.status()
    assert "spent" in s or "500" in s or "10000" in s


def test_tracker_reset():
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10_000)
    t.record("ping", 500)
    t.record_skip("screenshot")
    t.reset()
    assert t.spent == 0
    assert t.skipped == {}


# ── Router ────────────────────────────────────────────────────────────────────

def test_router_run_at_low_pct():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=100_000)
    r = ToolRouter(t)
    d = r.decide("get_component", {"path": "/UI"})
    assert d.action == "run"


def test_router_skip_at_95_pct_mid_tier():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10_000)
    t.record("filler", 9_600)  # 96%
    r = ToolRouter(t)
    d = r.decide("diagnose_object", {"path": "/UI"})
    assert d.action in ("skip", "downgrade")


def test_router_downgrade_screenshot_to_analyze_visual():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=1_000)
    t.record("filler", 990)  # near full
    r = ToolRouter(t)
    d = r.decide("screenshot", {})
    # screenshot is expensive, should downgrade to analyze_visual (has downgrade set)
    assert d.action == "downgrade"
    assert d.target == "analyze_visual"


def test_router_hint_at_50_expensive():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    # cap large enough so remaining (30k) > screenshot cost (12400), but >50% spent
    t = BudgetTracker(cap=100_000)
    t.record("filler", 60_000)  # 60% spent, 40k remaining > 12400
    r = ToolRouter(t)
    d = r.decide("screenshot", {})
    assert d.action == "run"
    assert d.hint  # hint should mention budget percentage


def test_router_skip_at_80_expensive_no_downgrade():
    from luna_mcp.budget import registry as reg
    from luna_mcp.budget.router import ToolCost, ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    # Patch a tool without downgrade that is expensive
    original = reg.TOOL_COSTS.get("audit_textures")
    reg.TOOL_COSTS["__test_exp__"] = ToolCost(400, 5000, "expensive", None)
    try:
        t = BudgetTracker(cap=10_000)
        t.record("filler", 8_500)  # 85%
        r = ToolRouter(t)
        d = r.decide("__test_exp__", {})
        assert d.action == "skip"
    finally:
        del reg.TOOL_COSTS["__test_exp__"]


def test_router_hard_stop_proj_over_remaining():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=500)
    t.record("filler", 490)  # 10 remaining, screenshot costs 12400
    r = ToolRouter(t)
    d = r.decide("screenshot", {})
    assert d.action in ("downgrade", "skip")


# ── Visual Router ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_visual_router_geometry_q_calls_canvasinfo():
    from luna_mcp.budget.visual_router import analyze_visual
    mock_call = AsyncMock(return_value="canvas_data")
    with patch("luna_mcp.budget.visual_router._call_fn", mock_call):
        result = await analyze_visual("what is the button position?")
    mock_call.assert_called_once()
    assert "getCanvasInfo" in mock_call.call_args[0]


@pytest.mark.asyncio
async def test_visual_router_color_q_calls_materials():
    from luna_mcp.budget.visual_router import analyze_visual
    mock_call = AsyncMock(return_value="material_data")
    with patch("luna_mcp.budget.visual_router._call_fn", mock_call):
        result = await analyze_visual("what color is the button material?")
    mock_call.assert_called_once()
    assert "getMaterials" in mock_call.call_args[0]


@pytest.mark.asyncio
async def test_visual_router_fallback_to_visual_summary():
    from luna_mcp.budget.visual_router import analyze_visual
    mock_call = AsyncMock(return_value="summary_data")
    with patch("luna_mcp.budget.visual_router._call_fn", mock_call):
        result = await analyze_visual("what is happening in the game?")
    mock_call.assert_called_once()
    # Should call visualSummary as fallback
    assert "visualSummary" in mock_call.call_args[0]


# ── ENV disable ───────────────────────────────────────────────────────────────

def test_disabled_env_always_runs():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    t = BudgetTracker(cap=10)  # tiny cap
    t.record("filler", 10)     # 100%
    r = ToolRouter(t)
    with patch.dict(os.environ, {"LUNA_BUDGET_DISABLED": "1"}):
        d = r.decide("screenshot", {})
    assert d.action == "run"


# ── Presets ───────────────────────────────────────────────────────────────────

def test_warmup_preset_5k_cap():
    from luna_mcp.budget.tracker import PRESETS, BudgetTracker
    t = BudgetTracker(cap=PRESETS["warmup"])
    assert t.cap == 5_000


def test_set_budget_mode_switch():
    from luna_mcp.budget import init_budget
    with patch.dict(os.environ, {"LUNA_BUDGET_MODE": "warmup"}):
        tracker, router = init_budget()
    assert tracker.cap == 5_000


# ── Compose order: budget → (reflect | guard) ─────────────────────────────────

@pytest.mark.asyncio
async def test_compose_budget_gates_before_inner():
    """budget gate fires FIRST — inner fn never called when skip."""
    from luna_mcp.budget.registry import ToolCost
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker

    inner_called = []
    async def inner_fn(**kw): inner_called.append(kw); return "inner"

    t = BudgetTracker(cap=100)
    t.record("filler", 100)  # exhausted
    router = ToolRouter(t)

    # inject test tool into registry so router can look it up
    from luna_mcp.budget import registry as reg
    reg.TOOL_COSTS["__test_skip__"] = ToolCost(200, 5000, "expensive", None)
    try:
        # simulate _gated manually
        from luna_mcp.server import _gated
        gated_fn = _gated("__test_skip__", inner_fn, router, t, {})
        result = await gated_fn()
        assert inner_called == [], "inner should NOT be called when budget exhausted"
        assert "skipped" in result
    finally:
        del reg.TOOL_COSTS["__test_skip__"]


@pytest.mark.asyncio
async def test_compose_budget_records_after_inner():
    """When action=run, tracker.record is called with the tool's est_in + out_tokens."""
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker

    async def inner_fn(**kw): return "hello world"

    t = BudgetTracker(cap=100_000)
    router = ToolRouter(t)
    from luna_mcp.server import _gated
    gated_fn = _gated("ping", inner_fn, router, t, {})

    # ping is budget-own but _gated still works if called directly
    with patch.dict(os.environ, {"LUNA_BUDGET_DISABLED": "0"}):
        result = await gated_fn()
    assert result == "hello world"
    # spent > 0 only if tracker.record was called (ping has est_in=20)
    assert t.spent > 0


# ── M1: set_budget updates the router used by _gated ─────────────────────────

@pytest.mark.asyncio
async def test_set_budget_actually_updates_router_decisions():
    """set_budget('warmup') caps at 5000; expensive tool at 4500 spent gets skipped (M1)."""
    # Use the module-level tracker/router (the ones _gated closure captures)
    import luna_mcp.server as srv
    from luna_mcp.budget import registry as reg
    from luna_mcp.budget.registry import ToolCost
    from luna_mcp.server import _gated

    orig_cap = srv._budget_tracker.cap
    orig_spent = srv._budget_tracker.spent
    try:
        # Simulate set_budget("warmup"): cap=5000, reset
        srv._budget_tracker.cap = 5_000
        srv._budget_tracker.reset()
        # Record 4500 tokens — 90% of warmup cap
        srv._budget_tracker.record("filler", 4_500)

        reg.TOOL_COSTS["__m1_exp__"] = ToolCost(400, 5000, "expensive", None)
        inner = AsyncMock(return_value="inner_result")
        gated = _gated("__m1_exp__", inner, srv._budget_router, srv._budget_tracker, {})

        with patch.dict(os.environ, {"LUNA_BUDGET_DISABLED": "0"}):
            result = await gated()

        assert inner.call_count == 0, "expensive tool must be skipped at 90% warmup cap"
        assert "skipped" in result or "skip" in result.lower()
    finally:
        del reg.TOOL_COSTS["__m1_exp__"]
        srv._budget_tracker.cap = orig_cap
        srv._budget_tracker.reset()
        srv._budget_tracker.spent = orig_spent
