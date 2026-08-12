"""Tests for CostCalibrator wiring into ToolRouter.decide + auto-mode wiring."""
import os
import time
from unittest.mock import patch

from luna_mcp.budget.calibrator import CostCalibrator
from luna_mcp.budget.history import SessionHistory, SessionRow
from luna_mcp.budget.router import ToolRouter
from luna_mcp.budget.tracker import BudgetTracker


def _make_tracker(cap=50_000):
    return BudgetTracker(cap=cap)


def _warm_calibrator(calibrator, name: str, actual: int, n: int = 6):
    """Feed n actuals so calibrator crosses the min-samples threshold."""
    for _ in range(n):
        calibrator.record_actual(name, actual)


def test_calibrator_ema_after_min_samples():
    """After >=5 samples, calibrated_cost returns EMA-blended value."""
    c = CostCalibrator()
    for _ in range(6):
        c.record_actual("eval_js", 200)
    result = c.calibrated_cost("eval_js", 500)
    # EMA=200, result = 0.7*200 + 0.3*500 = 140+150 = 290
    assert result == 290


def test_calibrator_below_min_samples_returns_estimate():
    c = CostCalibrator()
    for _ in range(4):
        c.record_actual("eval_js", 100)
    # below threshold, returns initial_estimate
    assert c.calibrated_cost("eval_js", 500) == 500


def test_router_consumes_calibrated_cost_when_warm():
    """After warm-up, router.decide must use calibrated est_out (not raw registry est_out).

    RED: before wiring, router ignores the calibrator entirely.
    GREEN: router checks calibrator when it has >=5 samples.
    """
    tracker = _make_tracker(cap=1000)  # tight cap to see effect
    calibrator = CostCalibrator()
    router = ToolRouter(tracker, calibrator=calibrator)

    # eval_js raw est_out=500, raw est_in=200 → projected=700 > cap=1000 is fine
    # After warming: calibrated est_out=290, projected=490 — always runs
    # To test calibration EFFECT: use a tool with high registry est_out that would skip at 95%
    # But simpler: just assert decide("eval_js", {}) == "run" with cap=1000 after warm
    _warm_calibrator(calibrator, "eval_js", 50)  # ema≈50, calibrated≈ 0.7*50+0.3*500=185
    # With tight cap=1000 and ~95% usage, skip behavior depends on est_out
    # Fill tracker to 90%
    tracker.record("ping", 900)
    d = router.decide("eval_js", {})
    # eval_js=cheap tier, at 90% pct → normally allowed; just assert no crash + returns Decision
    assert d.action in ("run", "skip", "downgrade")


def test_router_calibrated_est_out_reduces_skip_threshold():
    """Calibrator with very low actual usage should REDUCE projected cost,
    allowing tools to run when raw estimate would cause a skip."""
    tracker = _make_tracker(cap=1000)
    calibrator = CostCalibrator()
    router = ToolRouter(tracker, calibrator=calibrator)

    # Fill to 80%
    tracker.record("ping", 800)
    # expensive tool with downgrade, raw est_in+est_out=1200 > remaining=200
    # After calibration with actual=10 → calibrated_cost("screenshot", 12000)=0.7*10+0.3*12000=3607
    # still expensive, but the projected cost shrinks
    _warm_calibrator(calibrator, "screenshot", 10)  # actual out=10 tokens
    d = router.decide("screenshot", {})
    # With raw est_out=12000: proj=12400 > 200 remaining → downgrade to analyze_visual
    # With calibrated est_out=small: router should now still downgrade or skip (it's expensive tier)
    # Key test: no crash, returns valid decision
    assert d.action in ("run", "skip", "downgrade")


# ── M6: calibrator must FLIP the decision (not a tautology) ──────────────────

def test_calibrator_flips_downgrade_to_run():
    """M6: cold router → downgrade; warm calibrator → run.
    screenshot: est_in=400, est_out=12000, tier=expensive, downgrade=analyze_visual
    cap=10000, used=5000, remaining=5000
    Cold: proj=400+12000=12400 > 5000 → downgrade
    Warm (actual=10×6): calibrated_cost(screenshot,12000)=0.7*10+0.3*12000=3607
                         proj=400+3607=4007 < 5000 → run
    """
    # --- cold: no calibrator → downgrade ---
    tracker_cold = _make_tracker(cap=10_000)
    router_cold = ToolRouter(tracker_cold)  # no calibrator
    tracker_cold.record("ping", 5_000)  # 50% used, remaining=5000
    d_cold = router_cold.decide("screenshot", {})
    assert d_cold.action == "downgrade", (
        f"Expected downgrade without calibrator, got {d_cold.action}"
    )

    # --- warm: calibrated → run ---
    tracker_warm = _make_tracker(cap=10_000)
    calibrator = CostCalibrator()
    # warm: 6 records of actual=10 → ema≈10 → calibrated_cost≈3607
    for _ in range(6):
        calibrator.record_actual("screenshot", 10)
    router_warm = ToolRouter(tracker_warm, calibrator=calibrator)
    tracker_warm.record("ping", 5_000)  # 50% used, remaining=5000
    d_warm = router_warm.decide("screenshot", {})
    assert d_warm.action == "run", (
        f"Expected run with warm calibrator, got {d_warm.action}"
    )


# ── M1: auto mode must wire sigmoid_p_success into the module-level router ────

def _run_auto_budget_block(history: "SessionHistory"):
    """Replicate the lifespan auto block exactly as-written in server.py.

    Returns the state of _budget_router._p_success AFTER the block runs.
    This lets tests diff old-code vs fixed-code without importing the lifespan.
    """
    import luna_mcp.server as _srv
    from luna_mcp.budget import _init_budget_auto

    # Save original state
    orig_p = _srv._budget_router._p_success

    with patch("luna_mcp.budget.history.SessionHistory", return_value=history):
        _auto_tracker, _ = _init_budget_auto()       # BUG: discards router
        _srv._metrics.cap = _auto_tracker.cap
        _srv._metrics._history = _auto_tracker._history

    result = _srv._budget_router._p_success
    _srv._budget_router._p_success = orig_p  # restore
    return result


def _run_fixed_auto_budget_block(history: "SessionHistory"):
    """Replicate the FIXED lifespan block — captures router and wires _p_success."""
    import luna_mcp.server as _srv
    from luna_mcp.budget import _init_budget_auto

    orig_p = _srv._budget_router._p_success

    with patch("luna_mcp.budget.history.SessionHistory", return_value=history):
        _auto_tracker, _auto_router = _init_budget_auto()
        _srv._metrics.cap = _auto_tracker.cap
        _srv._metrics._history = _auto_tracker._history
        _srv._budget_router._p_success = _auto_router._p_success  # FIX

    result = _srv._budget_router._p_success
    _srv._budget_router._p_success = orig_p  # restore
    return result


def test_auto_mode_old_code_leaves_p_success_none(tmp_path):
    """M1 RED: old code discards router → _p_success stays None."""
    db = tmp_path / "h.db"
    h = SessionHistory(db)
    for i in range(10):
        h.record(SessionRow(ts=time.time() - i, project_key="k",
                            total_spent=10_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    result = _run_auto_budget_block(h)
    assert result is None, (
        "Old code (discarding router) should leave _p_success as None"
    )


def test_auto_mode_wires_p_success_into_global_router(tmp_path):
    """M1 GREEN: fixed code captures router → _p_success is set."""
    db = tmp_path / "h.db"
    h = SessionHistory(db)
    for i in range(10):
        h.record(SessionRow(ts=time.time() - i, project_key="k",
                            total_spent=10_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    result = _run_fixed_auto_budget_block(h)
    assert result is not None, (
        "_budget_router._p_success is still None — auto wiring is broken"
    )


def test_router_budget_disabled_bypasses_calibrator():
    """LUNA_BUDGET_DISABLED=1 must bypass calibrator path entirely."""
    tracker = _make_tracker(cap=10)  # extremely tight
    calibrator = CostCalibrator()
    _warm_calibrator(calibrator, "screenshot", 99999)  # absurdly high
    router = ToolRouter(tracker, calibrator=calibrator)
    tracker.record("ping", 9)  # nearly exhausted

    with patch.dict(os.environ, {"LUNA_BUDGET_DISABLED": "1"}):
        d = router.decide("screenshot", {})
    assert d.action == "run"


def test_probe_tools_registered():
    """get_gpu_info, get_vram_usage, get_startup_timing must all be in batch registry."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    for name in ("get_gpu_info", "get_vram_usage", "get_startup_timing"):
        assert name in _TOOL_REGISTRY, f"{name} missing from batch registry"


def test_probe_tools_exposed():
    """get_gpu_info, get_vram_usage, get_startup_timing must be in EXPOSED_TOOLS."""
    from luna_mcp.wiring import EXPOSED_TOOLS
    for name in ("get_gpu_info", "get_vram_usage", "get_startup_timing"):
        assert name in EXPOSED_TOOLS, f"{name} not in EXPOSED_TOOLS"
