"""Tests for JakefilePlanner (Haiku DSL planning) — RED phase."""
import pytest

from luna_mcp.build_intel.index import build_index
from luna_mcp.build_intel.planner import JakefilePlanner, parse_dsl

SAMPLE_DSL = """\
PATCH id=lower_quality search=quality: 85 replace=quality: 65 count=1 anchor_before=jpeg
PATCH id=disable_particle search="pc.ParticleEmitter" replace="pc.ParticleStub" count=1
"""

SAMPLE_DSL_QUOTED = """\
PATCH id=test1 search="quality: 85" replace="quality: 65" count=1 anchor_before="jpeg"
"""


def make_index(tmp_path):
    j = tmp_path / "Jakefile.js"
    j.write_text("// v6\ntask('build', f);\nvar x = 'anchor_string_twelve';\n")
    return build_index(j)


class MockSampling:
    enabled = True

    async def plan(self, intent, system_prompt, ctx=""):
        return SAMPLE_DSL


class DisabledSampling:
    enabled = False


def test_parse_dsl_basic():
    ops = parse_dsl(SAMPLE_DSL)
    assert len(ops) == 2
    assert ops[0]["id"] == "lower_quality"
    assert ops[0]["search"] == "quality: 85"
    assert ops[0]["replace"] == "quality: 65"
    assert ops[0]["count"] == 1


def test_parse_dsl_quoted():
    ops = parse_dsl(SAMPLE_DSL_QUOTED)
    assert len(ops) == 1
    assert ops[0]["search"] == "quality: 85"
    assert ops[0]["anchor_before"] == "jpeg"


def test_parse_dsl_empty():
    assert parse_dsl("") == []
    assert parse_dsl("no patches here") == []


def test_parse_dsl_capped_at_5():
    many = "\n".join(
        f"PATCH id=x{i} search=s{i} replace=r{i} count=1" for i in range(10)
    )
    ops = parse_dsl(many)
    assert len(ops) <= 5


def test_parse_dsl_skips_missing_required():
    # missing replace
    bad = "PATCH id=x search=foo count=1"
    assert parse_dsl(bad) == []


@pytest.mark.asyncio
async def test_planner_returns_dsl(tmp_path):
    idx = make_index(tmp_path)
    planner = JakefilePlanner(MockSampling())
    result = await planner.plan("reduce build size", idx)
    assert result == SAMPLE_DSL


@pytest.mark.asyncio
async def test_planner_disabled_returns_none(tmp_path):
    idx = make_index(tmp_path)
    planner = JakefilePlanner(DisabledSampling())
    result = await planner.plan("reduce build size", idx)
    assert result is None


@pytest.mark.asyncio
async def test_planner_none_sampling_returns_none(tmp_path):
    idx = make_index(tmp_path)
    planner = JakefilePlanner(None)
    result = await planner.plan("reduce build size", idx)
    assert result is None


@pytest.mark.asyncio
async def test_planner_exception_returns_none(tmp_path):
    class FailSampling:
        enabled = True
        async def plan(self, *a, **kw):
            raise RuntimeError("boom")

    idx = make_index(tmp_path)
    planner = JakefilePlanner(FailSampling())
    result = await planner.plan("intent", idx)
    assert result is None


# --- m4: malformed count is dropped (key skipped, caller uses default) ---

def test_parse_dsl_drops_malformed_count():
    dsl = "PATCH id=x search=foo replace=bar count=abc"
    ops = parse_dsl(dsl)
    assert len(ops) == 1
    # count key should be absent (dropped) — caller falls back to expected_count=1
    assert "count" not in ops[0]
