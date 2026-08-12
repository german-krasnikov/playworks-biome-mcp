"""Tests for budget registry coverage — EXPOSED_TOOLS ⊆ TOOL_COSTS regression guard."""
from luna_mcp.budget.registry import DEFAULT, TOOL_COSTS
from luna_mcp.wiring import EXPOSED_TOOLS


def test_exposed_tools_all_have_cost_entries():
    """PERMANENT REGRESSION GUARD: every exposed tool must have an explicit cost entry.
    Prevents future tools from silently falling through to DEFAULT."""
    missing = EXPOSED_TOOLS - set(TOOL_COSTS.keys())
    assert not missing, f"EXPOSED tools missing from TOOL_COSTS: {sorted(missing)}"


def test_tool_costs_has_minimum_coverage():
    """TOOL_COSTS must cover at least all current known exposed tools count."""
    assert len(TOOL_COSTS) >= 110, f"TOOL_COSTS only has {len(TOOL_COSTS)} entries"


def test_all_tool_costs_have_valid_tiers():
    valid_tiers = {"trivial", "cheap", "mid", "expensive"}
    for name, cost in TOOL_COSTS.items():
        assert cost.tier in valid_tiers, f"{name} has invalid tier {cost.tier!r}"
        assert cost.est_in > 0, f"{name} has non-positive est_in"
        assert cost.est_out > 0, f"{name} has non-positive est_out"


def test_default_cost_unchanged():
    """DEFAULT must stay as a stable fallback."""
    assert DEFAULT.est_in == 150
    assert DEFAULT.est_out == 800
    assert DEFAULT.tier == "mid"
