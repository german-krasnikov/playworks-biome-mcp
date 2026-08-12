from unittest.mock import AsyncMock, Mock

import pytest

from luna_mcp.source_mapper import SourceMapper


@pytest.fixture
def mock_bridge():
    bridge = Mock()
    bridge._scripts = {}
    bridge.send_cdp = AsyncMock(return_value={"result": {}})
    return bridge


@pytest.fixture
def mock_debugger():
    dbg = Mock()
    dbg.enable = AsyncMock()
    return dbg


@pytest.fixture
def mapper(mock_bridge, mock_debugger):
    return SourceMapper(mock_bridge, mock_debugger)


# ── _parse_frames ────────────────────────────────────────────────────────────

def test_parse_frames_chrome_format(mapper):
    stack = "    at Game.Player.Update (UnityScriptsCompiler.js:67890:5)"
    frames = mapper._parse_frames(stack)
    assert len(frames) == 1
    assert frames[0]["func"] == "Game.Player.Update"
    assert frames[0]["file"] == "UnityScriptsCompiler.js"
    assert frames[0]["line"] == 67890
    assert frames[0]["col"] == 5


def test_parse_frames_empty(mapper):
    assert mapper._parse_frames("no frames here") == []
    assert mapper._parse_frames("") == []


def test_parse_frames_with_column(mapper):
    stack = "at Foo.Bar.Baz (script.js:100:42)"
    frames = mapper._parse_frames(stack)
    assert frames[0]["col"] == 42


def test_parse_frames_multiple(mapper):
    stack = (
        "TypeError: null\n"
        "    at Bridge.Reflection.midel.$ctor1 (UnityScriptsCompiler.js:12345:1)\n"
        "    at Game.Characters.HeroController_V1.Update (UnityScriptsCompiler.js:67890:5)\n"
    )
    frames = mapper._parse_frames(stack)
    assert len(frames) == 2
    assert frames[0]["func"] == "Bridge.Reflection.midel.$ctor1"
    assert frames[1]["func"] == "Game.Characters.HeroController_V1.Update"


def test_parse_frames_no_column(mapper):
    stack = "at Game.Player.Update (UnityScriptsCompiler.js:100)"
    frames = mapper._parse_frames(stack)
    assert frames[0]["col"] is None


# ── _classify_frame ──────────────────────────────────────────────────────────

def test_classify_frame_csharp(mapper):
    assert mapper._classify_frame("Game.Player.Update") == "csharp"


def test_classify_frame_bridge(mapper):
    assert mapper._classify_frame("Bridge.Reflection.midel") == "bridge"


def test_classify_frame_system(mapper):
    assert mapper._classify_frame("System.String.Concat") == "system"


def test_classify_frame_unknown(mapper):
    assert mapper._classify_frame("anonymous") == "unknown"


# ── _find_script_id ──────────────────────────────────────────────────────────

def test_find_script_id_found(mapper, mock_bridge):
    mock_bridge._scripts = {
        "http://localhost:8000/UnityScriptsCompiler.js": "42",
        "http://localhost:8000/main.js": "1",
    }
    assert mapper._find_script_id("UnityScriptsCompiler") == "42"


def test_find_script_id_not_found(mapper, mock_bridge):
    mock_bridge._scripts = {}
    assert mapper._find_script_id("UnityScriptsCompiler") is None


# ── resolve_stack ────────────────────────────────────────────────────────────

async def test_resolve_stack_no_frames(mapper):
    result = await mapper.resolve_stack("no stack here")
    assert result == "No stack frames found"


async def test_resolve_stack_no_markers(mapper, mock_bridge):
    mock_bridge._scripts = {
        "http://localhost:8000/UnityScriptsCompiler.js": "42",
    }
    # searchInContent returns empty results
    mock_bridge.send_cdp.return_value = {"result": {"result": []}}
    stack = "at Game.Player.Update (UnityScriptsCompiler.js:67890:5)"
    result = await mapper.resolve_stack(stack)
    assert "#0" in result
    assert "Game.Player.Update" in result
    assert "67890" in result


async def test_resolve_stack_with_markers(mapper, mock_bridge):
    mock_bridge._scripts = {
        "http://localhost:8000/UnityScriptsCompiler.js": "42",
    }
    # First call: start marker, second call: end marker
    mock_bridge.send_cdp.side_effect = [
        {"result": {"result": [{"lineNumber": 67879, "lineContent": "/*...start.*/"}]}},
        {"result": {"result": [{"lineNumber": 67920, "lineContent": "/*...end.*/"}]}},
    ]
    stack = "at Game.Player.Update (UnityScriptsCompiler.js:67890:5)"
    result = await mapper.resolve_stack(stack)
    assert "67880" in result  # start_line = lineNumber + 1
    assert "67921" in result  # end_line = lineNumber + 1


async def test_resolve_stack_bridge_frame(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}
    mock_bridge.send_cdp.return_value = {"result": {"result": []}}
    stack = "at Bridge.Reflection.midel.$ctor1 (UnityScriptsCompiler.js:12345:1)"
    result = await mapper.resolve_stack(stack)
    assert "[bridge]" in result


# ── get_source_context ───────────────────────────────────────────────────────

async def test_get_source_context_no_script(mapper, mock_bridge):
    mock_bridge._scripts = {}
    result = await mapper.get_source_context("Game.Player", "Update")
    assert "not found" in result


async def test_get_source_context_no_marker(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}
    mock_bridge.send_cdp.return_value = {"result": {"result": []}}
    result = await mapper.get_source_context("Game.Player", "Update")
    assert "not found" in result.lower() or "marker" in result.lower()


async def test_get_source_context_found(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}
    source_lines = ["line0"] + [f"code line {i}" for i in range(1, 30)]
    source_text = "\n".join(source_lines)

    def send_side_effect(method, params=None, *args, **kwargs):
        if method == "Debugger.searchInContent":
            query = params.get("query", "")
            if "start" in query:
                return {"result": {"result": [{"lineNumber": 2, "lineContent": "/*start*/"}]}}
            return {"result": {"result": [{"lineNumber": 10, "lineContent": "/*end*/"}]}}
        if method == "Debugger.getScriptSource":
            return {"result": {"scriptSource": source_text}}
        return {"result": {}}

    mock_bridge.send_cdp = AsyncMock(side_effect=send_side_effect)
    result = await mapper.get_source_context("Game.Player", "Update")
    assert "Game.Player.Update" in result
    assert ":" in result  # line numbers present


# ── find_method ──────────────────────────────────────────────────────────────

async def test_find_method_not_found(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}
    mock_bridge.send_cdp.return_value = {"result": {"result": []}}
    result = await mapper.find_method("Game.Player", "Update")
    assert "not found" in result.lower()


async def test_find_method_with_markers(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}

    def send_side_effect(method, params=None, *args, **kwargs):
        if method == "Debugger.searchInContent":
            query = params.get("query", "")
            if "start" in query:
                return {"result": {"result": [{"lineNumber": 99, "lineContent": "/*start*/"}]}}
            return {"result": {"result": [{"lineNumber": 139, "lineContent": "/*end*/"}]}}
        return {"result": {}}

    mock_bridge.send_cdp = AsyncMock(side_effect=send_side_effect)
    result = await mapper.find_method("Game.Player", "Update")
    assert "Game.Player.Update" in result
    assert "100" in result  # start: lineNumber + 1
    assert "140" in result  # end: lineNumber + 1
    assert "scriptId: 42" in result


async def test_find_method_fallback(mapper, mock_bridge):
    mock_bridge._scripts = {"http://localhost:8000/UnityScriptsCompiler.js": "42"}

    call_count = [0]

    def send_side_effect(method, params=None, *args, **kwargs):
        if method == "Debugger.searchInContent":
            query = params.get("query", "")
            call_count[0] += 1
            if "start." in query or "end." in query:
                return {"result": {"result": []}}
            # fallback: function name search
            return {"result": {"result": [
                {"lineNumber": 50, "lineContent": "Game.Player.Update = function()"},
            ]}}
        return {"result": {}}

    mock_bridge.send_cdp = AsyncMock(side_effect=send_side_effect)
    result = await mapper.find_method("Game.Player", "Update")
    assert "references" in result or "line 51" in result


# ── script tracking in CDPBridge ─────────────────────────────────────────────

def test_bridge_has_scripts_dict():
    from luna_mcp.cdp_bridge import CDPBridge
    bridge = CDPBridge()
    assert hasattr(bridge, "_scripts")
    assert isinstance(bridge._scripts, dict)


async def test_bridge_tracks_script_parsed():
    """Simulate _read_loop processing a Debugger.scriptParsed event."""
    import asyncio
    import json

    from luna_mcp.cdp_bridge import CDPBridge

    bridge = CDPBridge()

    # Feed a scriptParsed event through _read_loop directly
    event = json.dumps({
        "method": "Debugger.scriptParsed",
        "params": {
            "scriptId": "42",
            "url": "http://localhost:8000/UnityScriptsCompiler.js",
        }
    })

    messages = [event]
    idx = [0]

    class FakeWS:
        async def __aiter__(self):
            for msg in messages:
                yield msg

    bridge._ws = FakeWS()
    bridge._events = asyncio.Queue()
    await bridge._read_loop()

    assert bridge._scripts.get("http://localhost:8000/UnityScriptsCompiler.js") == "42"


# ── source_tools registration ────────────────────────────────────────────────

def test_source_tools_registration():
    from luna_mcp.tools.source_tools import register_source_tools
    mock_mcp = Mock()
    mock_mcp.tool = Mock(return_value=lambda f: f)
    mapper = Mock()
    tools = register_source_tools(mock_mcp, lambda: mapper)
    assert "resolve_stack_trace" in tools
    assert "get_source_context" in tools
    assert "find_method" in tools


async def test_resolve_stack_trace_tool():
    from luna_mcp.tools.source_tools import register_source_tools
    mock_mcp = Mock()
    mock_mapper = Mock()
    mock_mapper.resolve_stack = AsyncMock(return_value="#0 Game.Player.Update\n   JS: script.js:100")

    tools = register_source_tools(mock_mcp, lambda: mock_mapper)
    fn, _ = tools["resolve_stack_trace"]
    result = await fn(stack_text="at Game.Player.Update (script.js:100:0)")
    assert "Game.Player.Update" in result
