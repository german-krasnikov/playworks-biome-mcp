"""Tests for optimize MCP tools (F10)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from luna_mcp.optimize_macro.orchestrator import BuildOptimizer
from luna_mcp.tools import optimize_tools as _mod


def _make_orchestrator(total_save=300):
    """Return BuildOptimizer with mocked subsystems returning fixed savings."""
    async def jf(intent):
        return "PATCH id=a\nPATCH id=b"

    async def pc(target_kb):
        return f"(save {total_save // 3}kb, conf 0.9)"

    async def asset(path, target_kb):
        return f"total_save={total_save // 3}kb actions=2"

    return BuildOptimizer(jakefile_suggest_fn=jf, pc_recommend_fn=pc, asset_recommend_fn=asset)


# ---- optimize_build_size ----

@pytest.mark.asyncio
async def test_optimize_build_size_returns_plan_text(monkeypatch):
    orch = _make_orchestrator(300)
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_build_size(300, "")
    assert "target_save_kb=300" in result
    assert "estimated_total=" in result


@pytest.mark.asyncio
async def test_optimize_invalid_target_zero(monkeypatch):
    monkeypatch.setattr(_mod, "_orchestrator", _make_orchestrator())
    result = await _mod.optimize_build_size(0, "")
    assert "INVALID" in result


@pytest.mark.asyncio
async def test_optimize_invalid_target_negative(monkeypatch):
    monkeypatch.setattr(_mod, "_orchestrator", _make_orchestrator())
    result = await _mod.optimize_build_size(-5, "")
    assert "INVALID" in result


@pytest.mark.asyncio
async def test_optimize_invalid_target_too_large(monkeypatch):
    monkeypatch.setattr(_mod, "_orchestrator", _make_orchestrator())
    result = await _mod.optimize_build_size(99999, "")
    assert "INVALID" in result


@pytest.mark.asyncio
async def test_optimize_degraded_when_no_orchestrator(monkeypatch):
    monkeypatch.setattr(_mod, "_orchestrator", None)
    result = await _mod.optimize_build_size(300, "")
    assert "DEGRADED" in result


@pytest.mark.asyncio
async def test_optimize_with_asset_path(monkeypatch):
    orch = _make_orchestrator(300)
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_build_size(300, "/my/assets")
    assert "target_save_kb=300" in result


@pytest.mark.asyncio
async def test_optimize_boundary_1kb(monkeypatch):
    orch = _make_orchestrator(1)
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_build_size(1, "")
    assert "target_save_kb=1" in result


@pytest.mark.asyncio
async def test_optimize_boundary_50000kb(monkeypatch):
    orch = _make_orchestrator(50000)
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_build_size(50000, "")
    assert "target_save_kb=50000" in result


# ---- optimize_status ----

@pytest.mark.asyncio
async def test_optimize_status_lists_subsystems(monkeypatch):
    orch = BuildOptimizer(
        jakefile_suggest_fn=AsyncMock(return_value=""),
        pc_recommend_fn=AsyncMock(return_value=""),
        asset_recommend_fn=AsyncMock(return_value=""),
    )
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_status()
    assert "jakefile" in result
    assert "pc_modules" in result
    assert "assets" in result
    assert "available" in result


@pytest.mark.asyncio
async def test_optimize_status_shows_unavailable(monkeypatch):
    orch = BuildOptimizer()  # no fns
    monkeypatch.setattr(_mod, "_orchestrator", orch)
    result = await _mod.optimize_status()
    assert "unavailable" in result


@pytest.mark.asyncio
async def test_optimize_status_degraded_when_no_orchestrator(monkeypatch):
    monkeypatch.setattr(_mod, "_orchestrator", None)
    result = await _mod.optimize_status()
    assert "DEGRADED" in result


# ---- registration ----

def test_register_optimize_tools_returns_dict():
    mcp = MagicMock()
    result = _mod.register_optimize_tools(mcp, exposed=set())
    assert "optimize_build_size" in result
    assert "optimize_status" in result


def test_register_optimize_tools_with_orchestrator():
    mcp = MagicMock()
    orch = BuildOptimizer()
    result = _mod.register_optimize_tools(mcp, orchestrator=orch, exposed=set())
    assert _mod._orchestrator is orch
