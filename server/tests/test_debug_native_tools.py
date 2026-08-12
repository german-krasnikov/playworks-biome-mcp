"""Tests for F2 luna_debug native channel tools."""
import pathlib

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def __init__(self):
        self.registered = []

    def tool(self, **kw):
        def dec(fn):
            self.registered.append(fn.__name__)
            return fn
        return dec


# --- registration ---

def test_debug_tools_returns_2_entries():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools
    tools = register_debug_native_tools(FakeMCP(), None, exposed=set())
    assert len(tools) == 2
    assert "luna_debug_discover" in tools
    assert "luna_debug_invoke" in tools


# --- discover passthrough ---

@pytest.mark.asyncio
async def test_discover_passes_enumerateDebugger():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools
    calls = []

    async def fake_call(method, *args):
        calls.append(method)
        return "Animator: get, set\nLog: create"

    tools = register_debug_native_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["luna_debug_discover"]
    await fn()
    assert calls == ["enumerateDebugger"]


# --- invoke passthrough ---

@pytest.mark.asyncio
async def test_invoke_passes_args():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools
    calls = []

    async def fake_call(method, *args):
        calls.append((method,) + args)
        return "ok"

    tools = register_debug_native_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["luna_debug_invoke"]
    await fn(type="Animator", name="get", params_json="{}")
    assert calls[0] == ("invokeDebugger", "Animator", "get", "{}")


@pytest.mark.asyncio
async def test_invoke_default_params_json():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools
    calls = []

    async def fake_call(method, *args):
        calls.append(args)
        return "ok"

    tools = register_debug_native_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["luna_debug_invoke"]
    await fn(type="Animator", name="get")
    # default params_json should be "{}"
    assert calls[0][-1] == "{}"


# --- exposed vs batch-only ---

def test_discover_exposed_invoke_batch_only():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools
    mcp = FakeMCP()
    register_debug_native_tools(mcp, None, exposed={"luna_debug_discover"})
    # discover should be registered, invoke should not
    assert "luna_debug_discover" in mcp.registered
    assert "luna_debug_invoke" not in mcp.registered


# --- error surface ---

@pytest.mark.asyncio
async def test_invoke_bad_json_surfaces_error():
    from luna_mcp.tools.debug_native_tools import register_debug_native_tools

    async def fake_call(method, *args):
        return "error: invalid JSON params"

    tools = register_debug_native_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["luna_debug_invoke"]
    result = await fn(type="Animator", name="get", params_json="{bad json}")
    assert "error" in result


# --- JS presence ---

def test_enumerate_debugger_js_present():
    js = JS_PATH.read_text()
    assert 'enumerateDebugger' in js
    assert 'invokeDebugger' in js
