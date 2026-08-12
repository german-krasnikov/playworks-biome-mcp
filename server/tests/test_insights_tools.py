"""Tests for insights_tools (S2.1)."""
import pathlib

import pytest

_JS_FILE = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# --- factory ---

def test_insights_returns_3_entries():
    from luna_mcp.tools.insights_tools import register_insights_tools
    tools = register_insights_tools(FakeMCP(), None)
    assert len(tools) == 3
    assert "insights_state" in tools
    assert "insights_events" in tools
    assert "insights_record_start" in tools


# --- insights_state ---

@pytest.mark.asyncio
async def test_state_pi_absent():
    from luna_mcp.tools.insights_tools import register_insights_tools

    async def call_fn(method, *args):
        return "pi-absent"

    tools = register_insights_tools(FakeMCP(), call_fn)
    fn, _ = tools["insights_state"]
    result = await fn()
    assert "pi-absent" in result


@pytest.mark.asyncio
async def test_state_pi_not_initialized():
    from luna_mcp.tools.insights_tools import register_insights_tools

    async def call_fn(method, *args):
        return "pi-not-initialized"

    tools = register_insights_tools(FakeMCP(), call_fn)
    fn, _ = tools["insights_state"]
    result = await fn()
    assert "pi-not-initialized" in result


# --- insights_events ---

@pytest.mark.asyncio
async def test_events_passthrough():
    from luna_mcp.tools.insights_tools import register_insights_tools

    async def call_fn(method, *args):
        return "1|0.0|levelStart|{}"

    tools = register_insights_tools(FakeMCP(), call_fn)
    fn, _ = tools["insights_events"]
    result = await fn()
    assert "levelStart" in result


# --- insights_record_start (batch-only) ---

@pytest.mark.asyncio
async def test_record_start_idempotent():
    from luna_mcp.tools.insights_tools import register_insights_tools

    call_log = []
    async def call_fn(method, *args):
        call_log.append(method)
        return "already"

    tools = register_insights_tools(FakeMCP(), call_fn)
    fn, _ = tools["insights_record_start"]
    result = await fn()
    assert result in ("already", "installed")


def test_record_start_is_batch_only():
    """insights_record_start must NOT be in EXPOSED_TOOLS."""
    from luna_mcp.wiring import EXPOSED_TOOLS
    assert "insights_record_start" not in EXPOSED_TOOLS


def test_insights_state_is_exposed():
    from luna_mcp.wiring import EXPOSED_TOOLS
    assert "insights_state" in EXPOSED_TOOLS
    assert "insights_events" in EXPOSED_TOOLS


# --- JS contract ---

def test_js_piState_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "piState:" in text


def test_js_installInsightsRecorder_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "installInsightsRecorder:" in text


def test_js_getInsightEvents_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "getInsightEvents:" in text


# --- Major 1 guard: piState guard order ---

def test_js_piState_not_initialized_before_absent():
    """'pi-not-initialized' check (function guard) must appear before 'pi-absent' check."""
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("piState:")
    assert idx >= 0
    snippet = text[idx:idx+400]
    i_not_init = snippet.find("pi-not-initialized")
    i_absent = snippet.find("pi-absent")
    assert i_not_init >= 0, "pi-not-initialized not found in piState"
    assert i_absent >= 0, "pi-absent not found in piState"
    assert i_not_init < i_absent, "pi-not-initialized must precede pi-absent"
