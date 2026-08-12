"""Wave 4 review: TDD tests for C1, C2, M1, M2, minors."""
import asyncio
import os
from unittest.mock import MagicMock

import pytest

# ── C1: lifespan auto mode calls _init_budget_auto ───────────────────────────

def test_lifespan_auto_mode_sets_auto_cap(tmp_path, monkeypatch):
    """LUNA_BUDGET_MODE=auto must result in cap != 30_000 when history exists."""
    monkeypatch.setenv("LUNA_BUDGET_MODE", "auto")
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "c1-test-proj")

    # Pre-populate enough sessions so compute_cap returns != 30k
    from luna_mcp.budget.history import SessionHistory, SessionRow, get_project_key
    h = SessionHistory(tmp_path / "history.db")
    key = get_project_key()
    for i in range(10):
        h.record(SessionRow(ts=float(i), project_key=key,
                            total_spent=15_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    h.close()

    # Simulate what lifespan should do when mode == "auto"
    mode = os.environ.get("LUNA_BUDGET_MODE", "work")
    assert mode == "auto"

    from luna_mcp.budget import init_budget
    tracker, router = init_budget(mode)

    # cap should be derived from history (p95 of 15k * 1.2 = 18k), not 30k
    assert tracker.cap != 30_000
    assert tracker.cap > 0
    # _history must be attached
    assert hasattr(tracker, "_history")
    assert tracker._history is not None


def test_lifespan_auto_mode_via_init_budget(tmp_path, monkeypatch):
    """init_budget('auto') must attach _history to tracker."""
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "c1b-proj")
    from luna_mcp.budget import init_budget
    tracker, router = init_budget("auto")
    assert hasattr(tracker, "_history")


# ── C2: set_budget("auto") applies cap to tracker ────────────────────────────

def test_set_budget_auto_applies_cap_to_tracker(tmp_path, monkeypatch):
    """set_budget('auto') must update tracker.cap and reset spent."""
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "c2-test-proj")

    from luna_mcp.budget.history import SessionHistory, SessionRow, get_project_key
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker

    # Pre-populate 10 sessions at 15k
    h = SessionHistory(tmp_path / "history.db")
    key = get_project_key()
    for i in range(10):
        h.record(SessionRow(ts=float(i), project_key=key,
                            total_spent=15_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    h.close()

    tracker = BudgetTracker(cap=30_000)
    tracker.record("ping", 5_000)  # spent = 5k
    router = ToolRouter(tracker)

    from luna_mcp.tools.budget_tools import _set_budget_auto
    result = asyncio.run(_set_budget_auto(tracker, router, data_dir=tmp_path))

    # cap must have been updated from history
    assert tracker.cap != 30_000
    assert tracker.cap > 0
    assert "auto" in result
    # M3: spent counter must be reset
    assert tracker.spent == 0


def test_set_budget_auto_returns_cap_info(tmp_path, monkeypatch):
    """set_budget('auto') result must mention cap and session count."""
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "c2b-proj")

    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker

    tracker = BudgetTracker(cap=30_000)
    router = ToolRouter(tracker)

    from luna_mcp.tools.budget_tools import _set_budget_auto
    result = asyncio.run(_set_budget_auto(tracker, router, data_dir=tmp_path))
    assert "cap=" in result


def test_set_budget_tool_auto_applies_cap(tmp_path, monkeypatch):
    """set_budget MCP tool with 'auto' must propagate to tracker."""
    monkeypatch.setenv("LUNA_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUNA_PROJECT", "c2c-proj")

    from luna_mcp.budget.history import SessionHistory, SessionRow, get_project_key
    from luna_mcp.budget.router import ToolRouter
    from luna_mcp.budget.tracker import BudgetTracker
    from luna_mcp.tools.budget_tools import register_budget_tools

    h = SessionHistory(tmp_path / "history.db")
    key = get_project_key()
    for i in range(10):
        h.record(SessionRow(ts=float(i), project_key=key,
                            total_spent=15_000, cap=30_000,
                            skipped=0, downgraded=0, hit_cap=0, success=1))
    h.close()

    tracker = BudgetTracker(cap=30_000)
    router = ToolRouter(tracker)
    mcp = MagicMock()
    tools = register_budget_tools(mcp, tracker, router, exposed=frozenset())

    set_budget = tools["set_budget"][0]
    result = asyncio.run(set_budget("auto"))

    assert tracker.cap != 30_000
    assert tracker.spent == 0
    assert "auto" in result


# ── M1: rows ordering bug in autotune ────────────────────────────────────────

def test_compute_cap_uses_newest_sessions_desc_order():
    """DB returns DESC (newest first). compute_cap must use rows[:30] not rows[-30:]."""
    from luna_mcp.budget.autotune import compute_cap
    from luna_mcp.budget.history import SessionRow

    # Simulate DB returning rows newest-first (DESC):
    # - rows[0..19] = newest: all failures (hit_cap=1, success=0)
    # - rows[20..29] = older: all success
    newest_failures = [
        SessionRow(ts=float(29 - i), project_key="k", total_spent=10_000,
                   cap=10_000, skipped=0, downgraded=0, hit_cap=1, success=0)
        for i in range(20)
    ]
    older_success = [
        SessionRow(ts=float(9 - i), project_key="k", total_spent=10_000,
                   cap=10_000, skipped=0, downgraded=0, hit_cap=0, success=1)
        for i in range(10)
    ]
    rows_desc = newest_failures + older_success  # DESC order from DB

    cap_with_failures = compute_cap(rows_desc)

    # If bug exists (uses rows[-20:] = older success), no failure bump
    # Correct behavior: rows[:20] = newest failures → should trigger bump
    cap_without_failures = compute_cap(older_success)  # cold start fallback

    # When failures are in the newest 20, cap should be bumped
    assert cap_with_failures > cap_without_failures * 1.2


def test_estimate_p_success_uses_newest_rows_desc():
    """estimate_p_success must use rows[:20] (newest = index 0 in DESC result)."""
    from luna_mcp.budget.autotune import estimate_p_success
    from luna_mcp.budget.history import SessionRow

    # DESC: newest 10 = all success, older 20 = all failures
    newest_success = [
        SessionRow(ts=float(29 - i), project_key="k", total_spent=1000, cap=30000,
                   skipped=0, downgraded=0, hit_cap=0, success=1)
        for i in range(10)
    ]
    older_failures = [
        SessionRow(ts=float(19 - i), project_key="k", total_spent=1000, cap=30000,
                   skipped=0, downgraded=0, hit_cap=1, success=0)
        for i in range(20)
    ]
    rows_desc = newest_success + older_failures

    # rows[:20] = 10 success + 10 failure → p = 0.5
    # rows[-20:] = 10 failure + 10 failure (bug) → p = 0.0
    p = estimate_p_success(rows_desc)
    assert p == pytest.approx(0.5)


# ── M2: CostCalibrator wired to _observe ─────────────────────────────────────

def test_observe_calls_calibrator_record_actual():
    """_observe must call calibrator.record_actual after successful tool call."""
    from luna_mcp.budget.calibrator import CostCalibrator

    calibrator = CostCalibrator()
    called_with = {}

    original_record = calibrator.record_actual

    def tracking_record(name, tokens):
        called_with["name"] = name
        called_with["tokens"] = tokens
        original_record(name, tokens)

    calibrator.record_actual = tracking_record

    import luna_mcp.server as srv
    old_cal = getattr(srv, "_calibrator", None)
    srv._calibrator = calibrator

    async def fake_fn(**kw):
        return "hello world result"

    try:
        wrapped = srv._observe("test_tool", fake_fn, {}, ())
        asyncio.run(wrapped)
        assert called_with.get("name") == "test_tool"
        assert called_with.get("tokens", 0) > 0
    finally:
        srv._calibrator = old_cal


# ── m2: Recorder lock is held before None check ──────────────────────────────

def test_recorder_log_with_no_active_is_safe(tmp_path):
    """log() when not active must not raise (atomic None check inside lock)."""
    from luna_mcp.record.recorder import Recorder
    r = Recorder(tmp_path)
    # Not started — _active is None
    r.log("ping", {}, "result", 10)  # must not raise


def test_recorder_log_writes_when_active(tmp_path):
    """log() writes a line when recording is active."""
    from luna_mcp.record.recorder import Recorder
    r = Recorder(tmp_path)
    r.start("test_session")
    r.log("ping", {}, "pong", 5)
    r.stop()
    lines = (tmp_path / "test_session.jsonl").read_text().splitlines()
    assert len(lines) == 2  # header + 1 log line


# ── m4: _RECORDER_SKIP includes meta tools ───────────────────────────────────

def test_recorder_skip_includes_meta_tools():
    """_RECORDER_SKIP must include mcp_stats, set_budget, get_budget_status."""
    import luna_mcp.server as srv
    assert "mcp_stats" in srv._RECORDER_SKIP
    assert "set_budget" in srv._RECORDER_SKIP
    assert "get_budget_status" in srv._RECORDER_SKIP
