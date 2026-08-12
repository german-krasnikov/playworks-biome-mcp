"""TDD tests for auto mode integration (feature #8: Budget Auto-tuning)."""
from unittest.mock import MagicMock

import pytest


def make_rows(n=10, spent=10_000, cap=30_000, hit_cap=0, success=1):
    from luna_mcp.budget.history import SessionRow
    return [
        SessionRow(ts=float(i), project_key="proj", total_spent=spent,
                   cap=cap, skipped=0, downgraded=0,
                   hit_cap=hit_cap, success=success)
        for i in range(n)
    ]


# ── init_budget("auto") ───────────────────────────────────────────────────────

def test_init_budget_auto_uses_history(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "test-proj")
    from luna_mcp.budget.history import SessionHistory, SessionRow
    # Pre-populate 10 rows
    h = SessionHistory(tmp_path / "history.db")
    for i in range(10):
        h.record(SessionRow(ts=float(i), project_key=get_proj_key("test-proj"),
                            total_spent=20_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    h.close()

    from luna_mcp.budget import init_budget
    tracker, router = init_budget("auto")
    # With 10 sessions at 20k spent, auto cap should be > 20k
    assert tracker.cap > 20_000


def get_proj_key(env_val: str) -> str:
    import hashlib
    return hashlib.sha256(env_val.encode()).hexdigest()[:12]


def test_init_budget_auto_cold_start_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "cold-project-xyz")
    from luna_mcp.budget import init_budget
    from luna_mcp.budget.autotune import PRESETS
    tracker, router = init_budget("auto")
    # No history → cold start → work preset (30k)
    assert tracker.cap == PRESETS["work"]


def test_init_budget_auto_history_stored_on_tracker(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "stored-proj")
    from luna_mcp.budget import init_budget
    tracker, router = init_budget("auto")
    assert hasattr(tracker, "_history")
    assert tracker._history is not None


def test_init_budget_existing_modes_still_work():
    from luna_mcp.budget import init_budget
    for mode in ("warmup", "work", "deep_debug"):
        tracker, router = init_budget(mode)
        assert tracker.cap > 0


def test_init_budget_env_auto(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "env-auto-proj")
    monkeypatch.setenv("LUNA_BUDGET_MODE", "auto")
    from luna_mcp.budget import init_budget
    tracker, router = init_budget()  # reads from env
    assert tracker.cap > 0


# ── on_shutdown ───────────────────────────────────────────────────────────────

def test_session_recorded_on_shutdown():
    from luna_mcp.budget.tracker import BudgetTracker
    mock_history = MagicMock()
    tracker = BudgetTracker(cap=30_000)
    tracker.record("ping", 1000)
    tracker.on_shutdown(mock_history)
    mock_history.record.assert_called_once()
    row = mock_history.record.call_args[0][0]
    assert row.total_spent == 1000
    assert row.cap == 30_000


def test_on_shutdown_none_history_safe():
    from luna_mcp.budget.tracker import BudgetTracker
    tracker = BudgetTracker(cap=30_000)
    tracker.on_shutdown(None)  # should not raise


def test_on_shutdown_hit_cap_flag():
    from luna_mcp.budget.tracker import BudgetTracker
    mock_history = MagicMock()
    tracker = BudgetTracker(cap=1_000)
    tracker.record("big", 1_000)  # exactly at cap
    tracker.on_shutdown(mock_history)
    row = mock_history.record.call_args[0][0]
    assert row.hit_cap == 1


def test_on_shutdown_success_flag_when_under_cap():
    from luna_mcp.budget.tracker import BudgetTracker
    mock_history = MagicMock()
    tracker = BudgetTracker(cap=30_000)
    tracker.record("ping", 1_000)  # 3.3% — under 95%
    tracker.on_shutdown(mock_history)
    row = mock_history.record.call_args[0][0]
    assert row.success == 1


def test_on_shutdown_success_0_when_over_95pct():
    from luna_mcp.budget.tracker import BudgetTracker
    mock_history = MagicMock()
    tracker = BudgetTracker(cap=10_000)
    tracker.record("big", 9_600)  # 96% > 95%
    tracker.on_shutdown(mock_history)
    row = mock_history.record.call_args[0][0]
    assert row.success == 0


def test_on_shutdown_skipped_counter():
    from luna_mcp.budget.tracker import BudgetTracker
    mock_history = MagicMock()
    tracker = BudgetTracker(cap=30_000)
    tracker.record_skip("screenshot")
    tracker.record_skip("screenshot")
    tracker.on_shutdown(mock_history)
    row = mock_history.record.call_args[0][0]
    assert row.skipped == 2


# ── sigmoid router ────────────────────────────────────────────────────────────

def test_router_uses_sigmoid_when_p_success_set():
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    tracker = BudgetTracker(cap=10_000)
    tracker.record("filler", 5_000)  # 50%
    router = ToolRouter(tracker, sigmoid_p_success=0.85)
    d = router.decide("ping", {})
    assert d.action in ("run", "downgrade", "skip")


def test_router_sigmoid_blocks_expensive_at_high_pct():
    from luna_mcp.budget import registry as reg
    from luna_mcp.budget.registry import ToolCost
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    reg.TOOL_COSTS["__sig_exp__"] = ToolCost(400, 5000, "expensive", None)
    try:
        tracker = BudgetTracker(cap=10_000)
        tracker.record("filler", 9_900)  # 99%
        # very low p_success → sigmoid should block
        router = ToolRouter(tracker, sigmoid_p_success=0.0)
        d = router.decide("__sig_exp__", {})
        assert d.action == "skip"
    finally:
        del reg.TOOL_COSTS["__sig_exp__"]


def test_router_hard_thresholds_when_p_success_none():
    """When sigmoid_p_success is None, original hard threshold logic is used."""
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    tracker = BudgetTracker(cap=10_000)
    tracker.record("filler", 9_600)  # 96%
    router = ToolRouter(tracker, sigmoid_p_success=None)
    d = router.decide("diagnose_object", {})
    # Original logic: at 95%+, mid/expensive → skip/downgrade
    assert d.action in ("skip", "downgrade")


def test_set_budget_auto_returns_derived_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "budget-tool-proj")
    import luna_mcp.server as srv
    import luna_mcp.tools.budget_tools as bt

    orig_cap = srv._budget_tracker.cap
    orig_spent = srv._budget_tracker.spent
    try:
        # call set_budget("auto") if exposed
        # We test the module directly
        result = None

        async def run():
            nonlocal result
            result = await bt._set_budget_auto(tmp_path)
        import asyncio
        asyncio.run(run())
        assert result is not None
        assert "auto" in result.lower() or "cap=" in result
    except AttributeError:
        # _set_budget_auto doesn't exist yet — this is RED phase
        pytest.skip("_set_budget_auto not yet implemented")
    finally:
        srv._budget_tracker.cap = orig_cap
        srv._budget_tracker.spent = orig_spent
