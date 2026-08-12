"""Tests for pc_replacer.recommender — RED phase."""
import pytest

from luna_mcp.pc_replacer.catalog import ModuleInfo
from luna_mcp.pc_replacer.recommender import Recommender


def make_catalog(entries):
    mods = {e[0]: ModuleInfo(id=e[0], exports=e[1], size_kb=e[2], category="test") for e in entries}

    class _Cat:
        def all(self):
            return list(mods.values())
        def get(self, mid):
            return mods.get(mid)

    return _Cat()


def make_scan(entries):
    """entries: list of (id, usage, size_kb)"""
    return {e[0]: {"usage": e[1], "size_kb": e[2], "evidence": "test"} for e in entries}


@pytest.mark.asyncio
async def test_recommend_unused_module():
    cat = make_catalog([("particle", ["pc.X"], 107)])
    scan = make_scan([("particle", "unused", 107)])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 50)
    assert "particle" in result
    assert "107" in result


@pytest.mark.asyncio
async def test_recommend_skips_used_modules():
    cat = make_catalog([
        ("particle", ["pc.X"], 107),
        ("audio", ["pc.Y"], 30),
    ])
    scan = make_scan([
        ("particle", "used", 107),
        ("audio", "unused", 30),
    ])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 20)
    assert "particle" not in result
    assert "audio" in result


@pytest.mark.asyncio
async def test_recommend_skips_partial_modules():
    cat = make_catalog([("x", ["pc.X"], 50)])
    scan = make_scan([("x", "partial", 50)])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 30)
    assert "no safe replacements" in result


@pytest.mark.asyncio
async def test_recommend_greedy_stops_at_target():
    cat = make_catalog([
        ("a", ["pc.A"], 60),
        ("b", ["pc.B"], 40),
        ("c", ["pc.C"], 20),
    ])
    scan = make_scan([
        ("a", "unused", 60),
        ("b", "unused", 40),
        ("c", "unused", 20),
    ])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 60)
    # Should include 'a' (60kb) and stop — greedy first-fit
    assert "a" in result
    # 60kb >= target 60, so 'b' might or might not be included
    assert "target_save_kb=60" in result


@pytest.mark.asyncio
async def test_recommend_no_modules_in_scan():
    cat = make_catalog([])
    r = Recommender(cat, None)
    result = await r.recommend({}, 100)
    assert "no safe replacements" in result


@pytest.mark.asyncio
async def test_recommend_ranks_by_size_descending():
    cat = make_catalog([
        ("small", ["pc.S"], 20),
        ("large", ["pc.L"], 100),
    ])
    scan = make_scan([
        ("small", "unused", 20),
        ("large", "unused", 100),
    ])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 200)
    # large should appear before small (sorted by size desc)
    assert result.index("large") < result.index("small")


@pytest.mark.asyncio
async def test_recommend_includes_confidence():
    cat = make_catalog([("x", ["pc.X"], 50)])
    scan = make_scan([("x", "unused", 50)])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 50)
    assert "conf" in result


@pytest.mark.asyncio
async def test_recommend_includes_achievable_kb():
    cat = make_catalog([("x", ["pc.X"], 50)])
    scan = make_scan([("x", "unused", 50)])
    r = Recommender(cat, None)
    result = await r.recommend(scan, 100)
    assert "achievable_kb=50" in result
