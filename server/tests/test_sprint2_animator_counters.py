"""Tests for Sprint 2: S2.3 get_animator_graph, S2.4 get_luna_counters."""
import pathlib

import pytest

_JS_FILE = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# === S2.3 get_animator_graph ===

def test_playworks_dict_has_animator_graph():
    from luna_mcp.tools.playworks_tools import register_playworks_tools
    tools = register_playworks_tools(FakeMCP(), None)
    assert "get_animator_graph" in tools


@pytest.mark.asyncio
async def test_get_animator_graph_passthrough():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        assert method == "getAnimatorGraph"
        return "ANIMATOR_GRAPH: Player\n  layer[0]: Base Layer (weight=1)\n  state: Idle t=0.50"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_animator_graph"]
    result = await fn(path="Player")
    assert "ANIMATOR_GRAPH" in result or "layer" in result or "Idle" in result


@pytest.mark.asyncio
async def test_get_animator_graph_no_debugger():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        return "error: Debugger.Animator not available"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_animator_graph"]
    result = await fn(path="Player")
    assert "error" in result


def test_js_getAnimatorGraph_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "getAnimatorGraph:" in text


def test_js_getAnimatorGraph_uses_object_keys():
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getAnimatorGraph:")
    assert idx >= 0
    snippet = text[idx:idx+1500]
    assert "Object.keys" in snippet


def test_js_getAnimatorGraph_layerKeys_in_loop():
    """layerKeys must be referenced inside the loop body (not dead variable)."""
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getAnimatorGraph:")
    assert idx >= 0
    snippet = text[idx:idx+1500]
    # layerKeys used in loop condition and array access
    assert snippet.count("layerKeys[") >= 1


# === S2.4 get_luna_counters ===

def test_playworks_dict_has_luna_counters():
    from luna_mcp.tools.playworks_tools import register_playworks_tools
    tools = register_playworks_tools(FakeMCP(), None)
    assert "get_luna_counters" in tools


@pytest.mark.asyncio
async def test_get_luna_counters_passthrough():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        assert method == "getLunaCounters"
        return "drawCalls: 12\nmaterialSwitches: 3\nverticesCount: 1200"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_luna_counters"]
    result = await fn()
    assert "drawCalls" in result


@pytest.mark.asyncio
async def test_get_luna_counters_unavailable():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        return "error: app.counters not available"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_luna_counters"]
    result = await fn()
    assert "error" in result


def test_js_getLunaCounters_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "getLunaCounters:" in text


def test_js_getLunaCounters_reads_previous():
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getLunaCounters:")
    assert idx >= 0
    snippet = text[idx:idx+1500]
    assert ".previous" in snippet


def test_js_getLunaCounters_dev_only_label():
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getLunaCounters:")
    assert idx >= 0
    snippet = text[idx:idx+1500]
    assert "advancedMode" in snippet


# === version bump ===

def test_js_version_is_1_6_1():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "1.6.1" in text
