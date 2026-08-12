"""Tests for BuildOptimizer orchestrator (F10)."""
import pytest

from luna_mcp.optimize_macro.estimator import CombinedPlan
from luna_mcp.optimize_macro.orchestrator import DEFAULT_SPLIT, BuildOptimizer

# ---- helpers ----

async def _jakefile_fn(intent: str) -> str:
    return "PLAN:\n  [op1] foo=bar\n  [op2] baz=qux\nVALIDATION:\nPATCH id=op1"


async def _pc_fn(target_kb: int) -> str:
    return "top replacements:\n  physics -> stub (save 45kb, conf 0.9, safe)\n  sound -> stub (save 30kb, conf 0.8)"


async def _asset_fn(path: str, target_kb: int) -> str:
    return "total_save=80kb actions=3\n  tex1 resize 1024→512 save 40kb\n  tex2 compress save 40kb"


# ---- estimator unit tests ----

def test_parse_pc_extracts_save_kb():
    opt = BuildOptimizer()
    src = opt._parse_pc_response("  phys -> stub (save 45kb, conf 0.9)\n  snd -> stub (save 30kb)", 100)
    assert src.estimated_save_kb == 75
    assert src.actions_count == 2
    assert src.name == "pc_modules"


def test_parse_pc_empty_text():
    opt = BuildOptimizer()
    src = opt._parse_pc_response("no matches here", 100)
    assert src.estimated_save_kb == 0
    assert src.actions_count == 0


def test_parse_asset_extracts_total_save():
    opt = BuildOptimizer()
    src = opt._parse_asset_response("total_save=80kb actions=3", 100)
    assert src.estimated_save_kb == 80
    assert src.actions_count == 3
    assert src.name == "assets"


def test_parse_asset_missing_fields():
    opt = BuildOptimizer()
    src = opt._parse_asset_response("some text", 100)
    assert src.estimated_save_kb == 0
    assert src.actions_count == 0


def test_parse_jakefile_counts_patches():
    opt = BuildOptimizer()
    # regex counts both PATCH keywords AND [opX] bracket lines = 4 total
    text = "PLAN:\n  [op1] foo\n  [op2] bar\nVALIDATION:\nPATCH id=op1\nPATCH id=op2"
    src = opt._parse_jakefile_response(text, 60)
    assert src.actions_count == 4
    assert src.name == "jakefile"


def test_parse_jakefile_empty():
    opt = BuildOptimizer()
    src = opt._parse_jakefile_response("", 60)
    assert src.actions_count == 0
    assert src.estimated_save_kb == 0


# ---- orchestrator async tests ----

@pytest.mark.asyncio
async def test_orchestrator_calls_all_three_subsystems():
    calls = []

    async def jf(intent):
        calls.append("jakefile")
        return "PLAN:\nPATCH id=x"

    async def pc(target_kb):
        calls.append("pc")
        return "result (save 50kb, conf 0.9)"

    async def asset(path, target_kb):
        calls.append("asset")
        return "total_save=40kb actions=2"

    opt = BuildOptimizer(jakefile_suggest_fn=jf, pc_recommend_fn=pc, asset_recommend_fn=asset)
    plan = await opt.optimize(300, asset_path="/tmp/assets")
    assert "jakefile" in calls
    assert "pc" in calls
    assert "asset" in calls
    assert len(plan.sources) == 3


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_jakefile():
    opt = BuildOptimizer(jakefile_suggest_fn=None)
    plan = await opt.optimize(300, asset_path="")
    jf_src = next(s for s in plan.sources if s.name == "jakefile")
    assert "unavailable" in jf_src.summary


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_pc():
    opt = BuildOptimizer(pc_recommend_fn=None)
    plan = await opt.optimize(300, asset_path="")
    pc_src = next(s for s in plan.sources if s.name == "pc_modules")
    assert "unavailable" in pc_src.summary


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_asset_fn():
    """asset_recommend_fn=None → source.summary contains 'unavailable'."""
    bo = BuildOptimizer(jakefile_suggest_fn=None, pc_recommend_fn=None, asset_recommend_fn=None)
    plan = await bo.optimize(target_kb=300, asset_path="/some/path")
    asset_source = next(s for s in plan.sources if s.name == "assets")
    assert "unavailable" in asset_source.summary


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_asset_path():
    """fn provided but asset_path empty → source.summary contains 'unavailable'."""
    async def fake_asset(p, k): return "total_save=5kb actions=1"
    bo = BuildOptimizer(jakefile_suggest_fn=None, pc_recommend_fn=None, asset_recommend_fn=fake_asset)
    plan = await bo.optimize(target_kb=300, asset_path="")  # empty path
    asset_source = next(s for s in plan.sources if s.name == "assets")
    assert "unavailable" in asset_source.summary


@pytest.mark.asyncio
async def test_orchestrator_aggregates_savings():
    async def jf(intent):
        return "PLAN:\nPATCH id=x\nPATCH id=y\nPATCH id=z"  # 3 patches

    async def pc(target_kb):
        return "(save 50kb, conf 0.9)"

    async def asset(path, target_kb):
        return "total_save=30kb actions=1"

    opt = BuildOptimizer(jakefile_suggest_fn=jf, pc_recommend_fn=pc, asset_recommend_fn=asset)
    plan = await opt.optimize(300, asset_path="/assets")
    # pc=50, asset=30 at minimum (jakefile varies by heuristic)
    pc_src = next(s for s in plan.sources if s.name == "pc_modules")
    asset_src = next(s for s in plan.sources if s.name == "assets")
    assert pc_src.estimated_save_kb == 50
    assert asset_src.estimated_save_kb == 30


@pytest.mark.asyncio
async def test_orchestrator_error_in_subsystem_returns_error_summary():
    async def bad_fn(intent):
        raise ValueError("something went wrong")

    opt = BuildOptimizer(jakefile_suggest_fn=bad_fn)
    plan = await opt.optimize(300, asset_path="")
    jf_src = next(s for s in plan.sources if s.name == "jakefile")
    assert "error" in jf_src.summary.lower()


@pytest.mark.asyncio
async def test_orchestrator_custom_split():
    targets = {}

    async def jf(intent):
        # intent contains target_kb
        import re
        m = re.search(r"~(\d+)kb", intent)
        targets["jakefile"] = int(m.group(1)) if m else 0
        return ""

    async def pc(target_kb):
        targets["pc"] = target_kb
        return ""

    async def asset(path, target_kb):
        targets["asset"] = target_kb
        return ""

    opt = BuildOptimizer(jakefile_suggest_fn=jf, pc_recommend_fn=pc, asset_recommend_fn=asset)
    custom = {"jakefile": 0.50, "pc_modules": 0.30, "assets": 0.20}
    await opt.optimize(1000, asset_path="/x", split=custom)
    assert targets["jakefile"] == 500
    assert targets["pc"] == 300
    assert targets["asset"] == 200


@pytest.mark.asyncio
async def test_orchestrator_returns_combined_plan_type():
    opt = BuildOptimizer()
    plan = await opt.optimize(500, asset_path="")
    assert isinstance(plan, CombinedPlan)
    assert plan.target_kb == 500


def test_default_split_sums_to_one():
    total = sum(DEFAULT_SPLIT.values())
    assert abs(total - 1.0) < 0.01
