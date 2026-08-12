"""Tests for playground field tools (S6.3)."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock


def _make_playground_json(tmp_path: Path, fields: dict) -> Path:
    """Create a fake build structure with playground.json (stage4/develop/js/)."""
    pg_dir = tmp_path / "LunaTemp" / "stage4" / "develop" / "js"
    pg_dir.mkdir(parents=True)
    pg_file = pg_dir / "playground.json"
    pg_file.write_text(json.dumps({"fields": fields}))
    return tmp_path


# ── get_playground_fields ────────────────────────────────────────────────────

def test_get_playground_fields_returns_fields(tmp_path):
    """get_playground_fields reads and formats fields from playground.json."""
    import asyncio

    from luna_mcp.tools.build_tools import get_playground_fields

    _make_playground_json(tmp_path, {
        "gameplay": {"speed": {"type": "float", "defaultValue": "1.0", "title": "Speed"}}
    })
    result = asyncio.run(get_playground_fields(str(tmp_path)))
    assert "PLAYGROUND FIELDS" in result
    assert "speed" in result


def test_get_playground_fields_exposed():
    """get_playground_fields must be in EXPOSED_TOOLS."""
    from luna_mcp.wiring import EXPOSED_TOOLS
    assert "get_playground_fields" in EXPOSED_TOOLS


# ── set_playground_field ─────────────────────────────────────────────────────

def test_set_playground_field_calls_setfield():
    """set_playground_field delegates to call_fn('setField', ...) with correct args."""
    import asyncio

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="ok")

    tools = register_playground_tools(mock_mcp, call_fn,
                                      exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    result = asyncio.run(fn(path="Game", field="speed", value="2.0"))
    call_fn.assert_called_once()
    assert call_fn.call_args[0][0] == "setField"


def test_set_playground_field_not_persisted_disclaimer():
    """Output must contain 'session' or 'not persisted' disclaimer."""
    import asyncio

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="set ok")

    tools = register_playground_tools(mock_mcp, call_fn,
                                      exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    result = asyncio.run(fn(path="Game", field="speed", value="2.0"))
    # disclaimer must be in output
    assert any(word in result.lower() for word in ("session", "not persisted", "resets"))


def test_set_playground_field_exposed():
    """set_playground_field must be in EXPOSED_TOOLS."""
    from luna_mcp.wiring import EXPOSED_TOOLS
    assert "set_playground_field" in EXPOSED_TOOLS


def test_set_playground_field_in_batch_registry():
    """set_playground_field must be in batch registry."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    assert "set_playground_field" in _TOOL_REGISTRY


def test_no_override_channel_invented():
    """No A/B override channel (fabricated feature) — only session-only setField exists."""
    from luna_mcp.tools import playground_tools
    # Must not have any 'override_channel' or 'ab_override' attributes
    assert not hasattr(playground_tools, "override_channel")
    assert not hasattr(playground_tools, "ab_override")


# ── M5+M7: type inference — float/bool/int must produce correct fieldType ─────

def test_set_playground_field_float_uses_number_type():
    """M5: float string value → call_fn called with coerced float and 'number' type."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="ok")

    tools = register_playground_tools(mock_mcp, call_fn, exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    asyncio.run(fn(path="Game/Obj", field="speed", value="1.5"))
    # M7: assert full call signature including coerced value and inferred type
    call_fn.assert_called_once_with("setField", "Game/Obj", "PlaygroundFields", "speed", 1.5, "number")


def test_set_playground_field_bool_uses_boolean_type():
    """M5: 'true' string → call_fn called with True and 'boolean' type."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="ok")

    tools = register_playground_tools(mock_mcp, call_fn, exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    asyncio.run(fn(path="Game/Obj", field="enabled", value="true"))
    call_fn.assert_called_once_with("setField", "Game/Obj", "PlaygroundFields", "enabled", True, "boolean")


def test_set_playground_field_int_uses_number_type():
    """M5: integer string value → call_fn called with int and 'number' type."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="ok")

    tools = register_playground_tools(mock_mcp, call_fn, exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    asyncio.run(fn(path="Game/Obj", field="count", value="42"))
    call_fn.assert_called_once_with("setField", "Game/Obj", "PlaygroundFields", "count", 42, "number")


def test_set_playground_field_string_stays_string():
    """M5: plain string value → call_fn called with str and 'string' type."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="ok")

    tools = register_playground_tools(mock_mcp, call_fn, exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    asyncio.run(fn(path="Game/Obj", field="label", value="hello"))
    call_fn.assert_called_once_with("setField", "Game/Obj", "PlaygroundFields", "label", "hello", "string")


def test_set_playground_field_disclaimer_still_present():
    """M5/M7: session-only disclaimer must still be in output."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools.playground_tools import register_playground_tools

    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    call_fn = AsyncMock(return_value="set ok")

    tools = register_playground_tools(mock_mcp, call_fn, exposed={"set_playground_field"})
    fn, _ = tools["set_playground_field"]
    result = asyncio.run(fn(path="Game/Obj", field="speed", value="2.0"))
    assert "session-only" in result or "not persisted" in result


# ── M4: step_frame must be registered read_only=False ────────────────────────

def test_step_frame_registered_read_only_false():
    """M4: step_frame mutates game state (timeScale 0→1→0) — must NOT be read_only."""
    from unittest.mock import AsyncMock, Mock

    from luna_mcp.tools import _HAS_ANNOTATIONS
    from luna_mcp.tools.playworks_tools import register_playworks_tools

    mock_mcp = Mock()
    captured = {}

    def fake_tool(**kw):
        def decorator(fn):
            captured[fn.__name__] = kw
            return fn
        return decorator

    mock_mcp.tool = fake_tool
    call_fn = AsyncMock(return_value="ok")
    register_playworks_tools(mock_mcp, call_fn, exposed={"step_frame"})

    assert "step_frame" in captured, "step_frame was not registered"
    if _HAS_ANNOTATIONS:
        ann = captured["step_frame"].get("annotations")
        assert ann is not None, "step_frame has no annotations"
        assert ann.readOnlyHint is False, f"step_frame readOnlyHint should be False, got {ann.readOnlyHint}"
