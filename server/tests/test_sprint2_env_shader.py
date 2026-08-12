"""Tests for Sprint 2: S2.5 inspect_environment, S2.6 get_shader_variants."""
import pathlib

import pytest

_JS_FILE = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# === S2.5 inspect_environment ===

def test_playworks_dict_has_inspect_environment():
    from luna_mcp.tools.playworks_tools import register_playworks_tools
    tools = register_playworks_tools(FakeMCP(), None)
    assert "inspect_environment" in tools


@pytest.mark.asyncio
async def test_inspect_environment_passthrough():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        assert method == "getEnvironment"
        return "creativeName: MyGame\nlunaVersion: 7.1.0\nwidth: 1080\nheight: 1920"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["inspect_environment"]
    result = await fn()
    assert "creativeName" in result or "lunaVersion" in result


@pytest.mark.asyncio
async def test_inspect_environment_no_runtime():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        return "error: no Unity runtime"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["inspect_environment"]
    result = await fn()
    assert "error" in result


def test_js_getEnvironment_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "getEnvironment:" in text


def test_js_getEnvironment_has_per_property_try_catch():
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getEnvironment:")
    assert idx >= 0
    snippet = text[idx:idx+3000]
    assert snippet.count("try {") >= 3 or snippet.count("try{") >= 3


def test_js_getEnvironment_decomposes_safeArea():
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getEnvironment:")
    assert idx >= 0
    snippet = text[idx:idx+3000]
    assert ".width" in snippet


# === S2.6 get_shader_variants ===

def test_playworks_dict_has_shader_variants():
    from luna_mcp.tools.playworks_tools import register_playworks_tools
    tools = register_playworks_tools(FakeMCP(), None)
    assert "get_shader_variants" in tools


@pytest.mark.asyncio
async def test_get_shader_variants_passthrough():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        assert method == "getUnityShaderReport"
        return "unityShaders: 5\ntotalVariants: 42\ncompiled: 40"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_shader_variants"]
    result = await fn()
    assert "unityShaders" in result or "totalVariants" in result


@pytest.mark.asyncio
async def test_get_shader_variants_no_api():
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    async def call_fn(method, *args):
        return "error: no pc.UnityShader"

    tools = register_playworks_tools(FakeMCP(), call_fn)
    fn, _ = tools["get_shader_variants"]
    result = await fn()
    assert "error" in result


def test_js_getUnityShaderReport_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "getUnityShaderReport:" in text


def test_js_getUnityShaderReport_no_shaderVariantsLog():
    """Must NOT dump shaderVariantsLog (huge string)."""
    text = _JS_FILE.read_text(encoding="utf-8")
    idx = text.find("getUnityShaderReport:")
    assert idx >= 0
    snippet = text[idx:idx+800]
    assert "shaderVariantsLog" not in snippet
