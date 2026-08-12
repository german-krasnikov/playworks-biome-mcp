"""TDD: macro/planner.py + macro/whitelist.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── whitelist ────────────────────────────────────────────────────────────────

def test_whitelist_snapshot_format():
    from luna_mcp.macro.whitelist import reset_cache, snapshot
    reset_cache()
    reg = {"find_objects": None, "get_hierarchy": None, "set_property": None}
    result = snapshot(reg)
    assert "find_objects" in result
    assert "get_hierarchy" in result
    assert "|" in result


def test_whitelist_snapshot_sorted():
    from luna_mcp.macro.whitelist import reset_cache, snapshot
    reset_cache()
    reg = {"zzz": None, "aaa": None, "mmm": None}
    result = snapshot(reg)
    parts = [p.strip() for p in result.split("|")]
    assert parts == sorted(parts)


def test_whitelist_cache():
    from luna_mcp.macro.whitelist import reset_cache, snapshot
    reset_cache()
    reg1 = {"tool_a": None}
    reg2 = {"tool_b": None}
    r1 = snapshot(reg1)
    r2 = snapshot(reg2)  # cached — should return same as r1
    assert r1 == r2


def test_whitelist_reset_cache():
    from luna_mcp.macro.whitelist import reset_cache, snapshot
    reset_cache()
    reg1 = {"tool_a": None}
    r1 = snapshot(reg1)
    reset_cache()
    reg2 = {"tool_b": None}
    r2 = snapshot(reg2)
    assert r1 != r2


def test_read_only_tools_is_frozenset():
    from luna_mcp.macro.whitelist import READ_ONLY_TOOLS
    assert isinstance(READ_ONLY_TOOLS, frozenset)
    assert "find_objects" in READ_ONLY_TOOLS
    assert "set_property" not in READ_ONLY_TOOLS


# ── clean_dsl ────────────────────────────────────────────────────────────────

def test_clean_dsl_strips_fences():
    from luna_mcp.macro.planner import clean_dsl
    raw = "```\nfind_objects query=Test\n```"
    result = clean_dsl(raw)
    assert result == "find_objects query=Test"


def test_clean_dsl_strips_prose():
    from luna_mcp.macro.planner import clean_dsl
    raw = "Sure, here's the plan:\nfind_objects query=Test\nThat's it!"
    result = clean_dsl(raw)
    assert result == "find_objects query=Test"


def test_clean_dsl_keeps_command_lines():
    from luna_mcp.macro.planner import clean_dsl
    raw = "find_objects query=CTA\nget_object_detail path=Root/CTA"
    result = clean_dsl(raw)
    lines = result.split("\n")
    assert len(lines) == 2
    assert "find_objects" in lines[0]
    assert "get_object_detail" in lines[1]


def test_clean_dsl_max_lines_caps_12():
    from luna_mcp.macro.planner import clean_dsl
    raw = "\n".join("ping" for _ in range(20))
    result = clean_dsl(raw)
    assert len(result.split("\n")) <= 12


def test_clean_dsl_empty_input():
    from luna_mcp.macro.planner import clean_dsl
    assert clean_dsl("") == ""
    assert clean_dsl(None) == ""


def test_clean_dsl_strips_blank_lines():
    from luna_mcp.macro.planner import clean_dsl
    raw = "find_objects query=Test\n\n\nget_object_detail path=X"
    result = clean_dsl(raw)
    assert "\n\n" not in result


# ── plan_batch ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_batch_returns_empty_when_sampling_disabled():
    from luna_mcp.macro.planner import plan_batch
    sampling = MagicMock()
    sampling.enabled = False
    result = await plan_batch("find CTA button", "do", sampling, {"find_objects": None})
    assert result == ""


@pytest.mark.asyncio
async def test_plan_batch_returns_empty_when_sampling_none():
    from luna_mcp.macro.planner import plan_batch
    result = await plan_batch("find CTA button", "do", None, {"find_objects": None})
    assert result == ""


@pytest.mark.asyncio
async def test_plan_batch_invokes_sampling_with_kind_specific_prompt():
    from luna_mcp.macro.whitelist import reset_cache
    reset_cache()
    from luna_mcp.macro.planner import plan_batch
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="find_objects query=Test")
    reg = {"find_objects": None, "get_object_detail": None}
    await plan_batch("find CTA", "ask", sampling, reg)
    sampling.plan.assert_called_once()
    call_args = sampling.plan.call_args
    system_prompt = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("system_prompt", "")
    assert "READ-ONLY" in system_prompt or "NEVER" in system_prompt


@pytest.mark.asyncio
async def test_plan_batch_passes_whitelist_in_prompt():
    from luna_mcp.macro.whitelist import reset_cache
    reset_cache()
    from luna_mcp.macro.planner import plan_batch
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="ping")
    reg = {"my_special_tool": None}
    await plan_batch("do something", "do", sampling, reg)
    call_args = sampling.plan.call_args
    system_prompt = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("system_prompt", "")
    assert "my_special_tool" in system_prompt


@pytest.mark.asyncio
async def test_plan_batch_passes_ctx():
    from luna_mcp.macro.whitelist import reset_cache
    reset_cache()
    from luna_mcp.macro.planner import plan_batch
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="ping")
    await plan_batch("do something", "do", sampling, {}, ctx="extra context here")
    call_args = sampling.plan.call_args
    # ctx passed as third positional or keyword
    passed_ctx = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("ctx", "")
    assert "extra context here" in passed_ctx


@pytest.mark.asyncio
async def test_plan_batch_cleans_raw_output():
    from luna_mcp.macro.whitelist import reset_cache
    reset_cache()
    from luna_mcp.macro.planner import plan_batch
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="```\nfind_objects query=CTA\n```")
    result = await plan_batch("find CTA", "do", sampling, {"find_objects": None})
    assert "```" not in result
    assert "find_objects" in result
