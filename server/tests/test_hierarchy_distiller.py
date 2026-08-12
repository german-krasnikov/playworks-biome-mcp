"""Tests for F16 Hierarchy Distiller — TDD RED phase."""
from __future__ import annotations

import pytest

SMALL_HIERARCHY = """Main Camera [Camera, AudioListener]
Directional Light [Light]
Player [Rigidbody, PlayerController]"""

LARGE_HIERARCHY = "\n".join(
    [f"Object{i} [MeshRenderer, Collider]" for i in range(60)]
    + [f"  Child{i} [Transform] !" for i in range(20)]
    + [f"InactiveObj{i} [] !" for i in range(10)]
)

NESTED_HIERARCHY = """Root [Transform]
  Child1 [MeshRenderer]
    GrandChild [SphereCollider] !
  Child2 [Light]
    Deep [Camera]
      Deeper [AudioListener]"""


# ── Tier 1 stats ──────────────────────────────────────────────────────────────

def test_distill_tier1_counts_objects():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1
    stats = distill_tier1(SMALL_HIERARCHY)
    assert stats["total"] == 3


def test_distill_tier1_counts_components():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1
    stats = distill_tier1(SMALL_HIERARCHY)
    assert stats["components"]["Camera"] == 1
    assert stats["components"]["AudioListener"] == 1
    assert stats["components"]["Light"] == 1


def test_distill_tier1_counts_inactive():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1
    stats = distill_tier1(LARGE_HIERARCHY)
    # 20 Child! + 10 InactiveObj! = 30
    assert stats["inactive"] == 30


def test_distill_tier1_max_depth():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1
    stats = distill_tier1(NESTED_HIERARCHY)
    assert stats["max_depth"] == 3  # Deeper is at 3 indent levels (6 spaces // 2)


def test_distill_tier1_empty():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1
    stats = distill_tier1("")
    assert stats["total"] == 0


# ── format_stats ──────────────────────────────────────────────────────────────

def test_format_stats_contains_total():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1, format_stats
    stats = distill_tier1(SMALL_HIERARCHY)
    out = format_stats(stats)
    assert "3" in out


def test_format_stats_contains_components():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1, format_stats
    stats = distill_tier1(SMALL_HIERARCHY)
    out = format_stats(stats)
    assert "Camera" in out


def test_format_stats_empty_scene():
    from luna_mcp.hierarchy_distiller.distiller import distill_tier1, format_stats
    stats = distill_tier1("")
    out = format_stats(stats)
    assert "Empty scene" in out


# ── distill_hierarchy tool ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_distill_below_threshold_returns_raw():
    from luna_mcp.tools.distiller_tools import distill_hierarchy
    result = await distill_hierarchy(SMALL_HIERARCHY, threshold=50)
    assert result == SMALL_HIERARCHY


@pytest.mark.asyncio
async def test_distill_above_threshold_returns_stats():
    from luna_mcp.tools.distiller_tools import distill_hierarchy
    result = await distill_hierarchy(LARGE_HIERARCHY, threshold=50)
    assert "Scene:" in result
    assert "objects" in result


@pytest.mark.asyncio
async def test_distill_empty_returns_empty_scene():
    from luna_mcp.tools.distiller_tools import distill_hierarchy
    result = await distill_hierarchy("", threshold=50)
    assert "Empty scene" in result


@pytest.mark.asyncio
async def test_distill_default_threshold_is_50():
    """Hierarchy with exactly 49 lines → returned raw."""
    hierarchy_49 = "\n".join(f"Obj{i} [Transform]" for i in range(49))
    from luna_mcp.tools.distiller_tools import distill_hierarchy
    result = await distill_hierarchy(hierarchy_49)
    assert result == hierarchy_49


@pytest.mark.asyncio
async def test_distill_tier1_only_no_sampling(monkeypatch):
    """Tier 2 disabled (no sampling) → Tier 1 stats returned."""
    from luna_mcp.tools import distiller_tools
    monkeypatch.setattr(distiller_tools, "_sampling", None)
    result = await distiller_tools.distill_hierarchy(LARGE_HIERARCHY, threshold=50)
    assert "Scene:" in result
    assert "Components:" in result


@pytest.mark.asyncio
async def test_distill_tier2_sampling_called(monkeypatch):
    """Tier 2 enabled (sampling present) → LLM anomalies appear in output."""
    from luna_mcp.tools import distiller_tools

    class FakeSampling:
        async def plan(self, intent: str, system: str, ctx: str = "") -> str:
            return "- Too many inactive objects\n- Unusual depth"

    monkeypatch.setattr(distiller_tools, "_sampling", FakeSampling())
    result = await distiller_tools.distill_hierarchy(LARGE_HIERARCHY, threshold=50)
    assert "[ANOMALIES]" in result
    assert "inactive objects" in result
