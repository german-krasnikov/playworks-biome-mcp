"""Tests for F18: Auto-Playtest Script Generator."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from luna_mcp.playtest.generator import (
    TEMPLATES,
    generate_playtest_script,
    match_template,
)

# ── match_template ────────────────────────────────────────────────────────────

def test_match_template_cta():
    result = match_template("test CTA button")
    assert result == TEMPLATES["cta"]


def test_match_template_load():
    result = match_template("check load performance")
    assert result == TEMPLATES["load"]


def test_match_template_orientation():
    result = match_template("test orientation change")
    assert result == TEMPLATES["orientation"]


def test_match_template_performance():
    result = match_template("run performance check")
    assert result == TEMPLATES["performance"]


def test_match_template_endcard():
    result = match_template("inspect endcard elements")
    assert result == TEMPLATES["endcard"]


def test_match_template_no_match():
    assert match_template("something unknown xyz") is None


def test_match_template_case_insensitive():
    result = match_template("Check CTA Button")
    assert result == TEMPLATES["cta"]


# ── generate_playtest_script — Tier 1 (no Haiku) ─────────────────────────────

@pytest.mark.asyncio
async def test_generate_tier1_cta():
    result = await generate_playtest_script("test CTA button", sampling=None)
    assert result == TEMPLATES["cta"]


@pytest.mark.asyncio
async def test_generate_no_template_no_haiku():
    result = await generate_playtest_script("something unknown", sampling=None)
    assert result == "[NO_TEMPLATE] Cannot generate script for: something unknown"


# ── generate_playtest_script — Tier 2 (Haiku) ────────────────────────────────

@pytest.mark.asyncio
async def test_generate_tier2_haiku_valid(monkeypatch):
    """Haiku returns valid DSL → returned as-is after dry_run."""
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="get_performance_metrics\nscreenshot")

    execute_batch_mock = AsyncMock(return_value="[DRY-RUN OK] all 2 steps validated")

    result = await generate_playtest_script(
        "check something custom",
        sampling=sampling,
        tool_registry={"get_performance_metrics": None, "screenshot": None},
        execute_batch_fn=execute_batch_mock,
    )
    assert "get_performance_metrics" in result
    assert "screenshot" in result


@pytest.mark.asyncio
async def test_generate_tier2_haiku_invalid_fallback_to_no_template(monkeypatch):
    """Haiku returns script, dry_run rejects → fallback to no-template message."""
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="fake_tool_xyz\nscreenshot")

    execute_batch_mock = AsyncMock(return_value="[BATCH ABORTED at step 1]\n[INVALID: fake_tool_xyz]")

    result = await generate_playtest_script(
        "check something custom",
        sampling=sampling,
        tool_registry={"screenshot": None},
        execute_batch_fn=execute_batch_mock,
    )
    assert "[NO_TEMPLATE]" in result


@pytest.mark.asyncio
async def test_generate_tier2_haiku_returns_none(monkeypatch):
    """Haiku returns None → fallback to no-template."""
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value=None)

    result = await generate_playtest_script(
        "check something custom",
        sampling=sampling,
    )
    assert "[NO_TEMPLATE]" in result


@pytest.mark.asyncio
async def test_generate_tier2_haiku_not_enabled():
    """Sampling exists but disabled → Tier 1 then no-template."""
    sampling = MagicMock()
    sampling.enabled = False

    result = await generate_playtest_script("check something custom", sampling=sampling)
    assert "[NO_TEMPLATE]" in result


# ── playtest_tools registration ───────────────────────────────────────────────

def test_register_playtest_tools_returns_dict():
    from unittest.mock import MagicMock

    from luna_mcp.tools.playtest_tools import register_playtest_tools

    mcp = MagicMock()
    exposed = {"generate_playtest"}

    result = register_playtest_tools(
        mcp,
        get_sampling=lambda: None,
        get_tool_registry=lambda: {},
        exposed=exposed,
    )
    assert "generate_playtest" in result
    assert "run_generated_playtest" in result


@pytest.mark.asyncio
async def test_generate_playtest_tool_cta():
    """generate_playtest tool returns CTA script for CTA intent."""
    from unittest.mock import MagicMock

    from luna_mcp.tools.playtest_tools import register_playtest_tools

    mcp = MagicMock()
    exposed = {"generate_playtest"}

    tools = register_playtest_tools(
        mcp,
        get_sampling=lambda: None,
        get_tool_registry=lambda: {},
        exposed=exposed,
    )
    fn, _ = tools["generate_playtest"]
    result = await fn(intent="test CTA button")
    assert result == TEMPLATES["cta"]


@pytest.mark.asyncio
async def test_run_generated_playtest_executes():
    """run_generated_playtest calls execute_batch with given script."""
    from unittest.mock import MagicMock

    from luna_mcp.tools.playtest_tools import register_playtest_tools

    mcp = MagicMock()
    exposed = set()
    executed = []

    async def fake_execute(script, **kwargs):
        executed.append(script)
        return "ok"

    tools = register_playtest_tools(
        mcp,
        get_sampling=lambda: None,
        get_tool_registry=lambda: {},
        exposed=exposed,
        execute_batch_fn=fake_execute,
    )
    fn, _ = tools["run_generated_playtest"]
    result = await fn(script="screenshot\nget_console level=E count=5")
    assert executed == ["screenshot\nget_console level=E count=5"]
    assert result == "ok"
