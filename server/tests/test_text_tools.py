"""Tests for F6 diagnose_text tool."""
import pathlib
import re

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# --- tool registration ---

def test_text_tools_returns_1_entry():
    from luna_mcp.tools.text_tools import register_text_tools
    tools = register_text_tools(FakeMCP(), None, exposed=set())
    assert len(tools) == 1
    assert "diagnose_text" in tools


# --- passthrough tests ---

@pytest.mark.asyncio
async def test_diagnose_text_passes_path():
    from luna_mcp.tools.text_tools import register_text_tools
    calls = []

    async def fake_call(method, *args):
        calls.append((method,) + args)
        return "Canvas/Label | text=Hello | overflow=False | overflowMode=Overflow"

    tools = register_text_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["diagnose_text"]
    await fn(path="/Canvas/Label")
    assert calls[0] == ("diagnoseText", "/Canvas/Label")


@pytest.mark.asyncio
async def test_no_tmp_component_passthrough():
    from luna_mcp.tools.text_tools import register_text_tools

    async def fake_call(method, *args):
        return "error: no TMP component on /Canvas/Label"

    tools = register_text_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["diagnose_text"]
    result = await fn(path="/Canvas/Label")
    assert "error: no TMP component" in result


@pytest.mark.asyncio
async def test_missing_glyph_passthrough():
    from luna_mcp.tools.text_tools import register_text_tools

    async def fake_call(method, *args):
        return "Canvas/Label | text=Hello | missing=é,ñ | overflow=False"

    tools = register_text_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["diagnose_text"]
    result = await fn(path="/Canvas/Label")
    assert "missing" in result


# --- JS presence ---

def test_has_character_present():
    js = JS_PATH.read_text()
    assert 'HasCharacter' in js


def test_has_character_no_third_true_arg():
    """HasCharacter must be called with 2 args (no tryAddCharacter mutation)."""
    js = JS_PATH.read_text()
    # Should NOT have HasCharacter(x, y, true) pattern
    assert not re.search(r'HasCharacter\([^)]+,\s*true\s*,\s*true', js)
    # Should have HasCharacter with 2 args
    assert re.search(r'HasCharacter\([^,]+,\s*true\)', js)


def test_diagnose_text_js_present():
    js = JS_PATH.read_text()
    assert 'diagnoseText' in js
    assert 'ForceMeshUpdate' in js
