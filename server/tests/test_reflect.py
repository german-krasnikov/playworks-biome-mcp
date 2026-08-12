"""Tests for Asymmetric Reflection middleware."""
import os
from unittest.mock import AsyncMock, patch

import pytest

# ── imports (will fail until modules exist) ───────────────────────────────────
from luna_mcp.reflect import (
    _RULES,
    _values_close,
    register_rule,
    with_reflect,
)

# ── test_registry_register_rule ───────────────────────────────────────────────

def test_registry_register_rule():
    before = len(_RULES)

    @register_rule("__test_cmd__")
    async def _rule(args, kw, response, call_fn):
        return None

    assert "__test_cmd__" in _RULES
    assert len(_RULES) == before + 1
    del _RULES["__test_cmd__"]  # cleanup


# ── test_set_property_match_silent ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_property_match_silent():
    import json

    import luna_mcp.reflect.rules_modify as rm
    snap = json.dumps({"ok": True, "exists": True, "value": 42})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="Root/Obj", component_type="Health", prop="hp", value="42"
    )
    rm._call_fn = orig
    assert result == "ok"
    assert "[REFLECT:" not in result


# ── test_set_property_mismatch_returns_marker ─────────────────────────────────

@pytest.mark.asyncio
async def test_set_property_mismatch_returns_marker():
    import json

    import luna_mcp.reflect.rules_modify as rm
    snap = json.dumps({"ok": True, "exists": True, "value": 99})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="Root/Obj", component_type="Health", prop="hp", value="42"
    )
    rm._call_fn = orig
    assert "[REFLECT:" in result
    assert "hp" in result


# ── test_set_property_destroyed_after_write ───────────────────────────────────

@pytest.mark.asyncio
async def test_set_property_destroyed_after_write():
    import json

    import luna_mcp.reflect.rules_modify as rm
    snap = json.dumps({"ok": True, "exists": False})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="Root/Obj", component_type="Health", prop="hp", value="42"
    )
    rm._call_fn = orig
    assert "[REFLECT:" in result
    assert "not found" in result


# ── test_set_transform_vector_close ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_transform_vector_close():
    import json

    import luna_mcp.reflect.rules_modify as rm
    # Within 1e-4 rel tolerance
    snap = json.dumps({"ok": True, "exists": True, "value": {"x": 1.0000001, "y": 2.0, "z": 3.0}})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_transform", fn)

    result = await wrapped(path="Root/Obj", prop="position", x=1.0, y=2.0, z=3.0)
    rm._call_fn = orig
    assert "[REFLECT:" not in result


# ── test_eval_js_skip_non_assignment ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_eval_js_skip_non_assignment():
    fn = AsyncMock(return_value="42")
    wrapped = with_reflect("eval_js", fn)

    result = await wrapped(expression="Math.random()")
    assert "[REFLECT:" not in result


# ── test_eval_js_assignment_verifies_via_ping ─────────────────────────────────

@pytest.mark.asyncio
async def test_eval_js_assignment_verifies_via_ping_ok():
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("eval_js", fn)

    result = await wrapped(expression="window.foo = 42")
    # ping would be called internally; since we mock fn, no real ping — just no crash
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_eval_js_assignment_verifies_via_ping_fail():
    """When ping returns empty/falsy after assignment → REFLECT marker."""
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("eval_js", fn)

    # Patch _call_fn inside rules_runtime so ping returns empty string
    import luna_mcp.reflect.rules_runtime as rr
    orig = rr._ping_fn
    rr._ping_fn = AsyncMock(return_value="")

    result = await wrapped(expression="window.foo = 42")
    rr._ping_fn = orig

    assert "[REFLECT:" in result


# ── test_no_reflect_arg_skips ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_reflect_arg_skips():
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="Root/Obj", component_type="Health", prop="hp", value="42",
        _no_reflect=True,
    )
    assert result == "ok"
    assert "[REFLECT:" not in result


# ── test_env_disabled_skips ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_env_disabled_skips():
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    with patch.dict(os.environ, {"LUNA_REFLECT": "0"}):
        result = await wrapped(
            path="Root/Obj", component_type="Health", prop="hp", value="42"
        )
    assert result == "ok"
    assert "[REFLECT:" not in result


# ── test_rule_crash_silent ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_crash_silent():
    @register_rule("__crash_cmd__")
    async def _rule(args, kw, response, call_fn):
        raise RuntimeError("boom")

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("__crash_cmd__", fn)

    result = await wrapped(x=1)
    assert result == "ok"  # no exception, no marker
    del _RULES["__crash_cmd__"]


# ── test_skip_on_error_response ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skip_on_error_response():
    fn = AsyncMock(return_value="Error: something went wrong")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="Root/Obj", component_type="Health", prop="hp", value="42"
    )
    assert "[REFLECT:" not in result


# ── test_with_reflect_composes_with_guard ─────────────────────────────────────

@pytest.mark.asyncio
async def test_with_reflect_composes_with_guard():
    """wrap_with_guard then with_reflect: guard blocks invalid args, reflect adds marker on mismatch."""
    import json

    from luna_mcp.middleware import wrap_with_guard
    from luna_mcp.schema_cache import SchemaCache
    from luna_mcp.schema_guard import SchemaGuard

    call_order = []

    async def base_fn(**kw):
        call_order.append("base")
        return "ok"

    # guard that always passes
    cache = SchemaCache()
    tm = AsyncMock()
    tm.is_loaded.return_value = False
    guard = SchemaGuard(cache, tm, AsyncMock(return_value="ok"))

    guarded_fn, params = wrap_with_guard(
        "set_property", base_fn,
        {"path": str, "component_type": str, "prop": str, "value": str},
        guard, None,
    )

    # set_property rule reads back: match → no marker
    snap = json.dumps({"ok": True, "exists": True, "value": 42})
    import luna_mcp.reflect.rules_modify as rm
    orig_call = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    reflected_fn = with_reflect("set_property", guarded_fn)
    result = await reflected_fn(
        path="/Root/Obj", component_type="Health", prop="hp", value="42"
    )
    rm._call_fn = orig_call

    assert "base" in call_order  # base ran
    assert "[REFLECT:" not in result  # values matched


# ── _values_close helpers ─────────────────────────────────────────────────────

def test_values_close_int_string():
    assert _values_close("42", 42)
    assert _values_close(42, "42")
    assert not _values_close("42", 99)


def test_values_close_float_tolerance():
    assert _values_close(1.0, 1.00001)
    assert not _values_close(1.0, 1.01)


def test_values_close_bool():
    assert _values_close(True, True)
    assert _values_close("true", True)
    assert not _values_close(True, False)


def test_values_close_dict_vector():
    assert _values_close({"x": 1.0, "y": 2.0, "z": 3.0}, {"x": 1.0, "y": 2.0, "z": 3.0})
    assert not _values_close({"x": 1.0, "y": 2.0, "z": 3.0}, {"x": 1.0, "y": 2.0, "z": 4.0})


# ── M2: physics props skip reflect ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_property_velocity_skipped():
    """set_property velocity (Rigidbody) must produce NO [REFLECT:] marker (M2)."""
    import json

    import luna_mcp.reflect.rules_modify as rm

    # readBack returns different value — would normally trigger REFLECT
    snap = json.dumps({"ok": True, "exists": True, "value": 5.0})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="/Root/Ball", component_type="Rigidbody", prop="velocity", value="10"
    )
    rm._call_fn = orig
    assert "[REFLECT:" not in result


@pytest.mark.asyncio
async def test_set_property_angular_velocity_skipped():
    """angularVelocity is also in skip-list — no reflect marker."""
    import json

    import luna_mcp.reflect.rules_modify as rm

    snap = json.dumps({"ok": True, "exists": True, "value": 0.0})
    orig = rm._call_fn
    rm._call_fn = AsyncMock(return_value=snap)

    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("set_property", fn)

    result = await wrapped(
        path="/Root/Ball", component_type="Rigidbody2D", prop="angularVelocity", value="5"
    )
    rm._call_fn = orig
    assert "[REFLECT:" not in result


# ── m3: eval_js assignment regex fixes ───────────────────────────────────────

@pytest.mark.asyncio
async def test_eval_js_skips_strict_inequality():
    """x !== y has no assignment — no verify triggered."""
    fn = AsyncMock(return_value="false")
    wrapped = with_reflect("eval_js", fn)
    import luna_mcp.reflect.rules_runtime as rr
    orig = rr._ping_fn
    rr._ping_fn = AsyncMock(return_value="pong")
    result = await wrapped(expression="x !== y")
    rr._ping_fn = orig
    assert "[REFLECT:" not in result


@pytest.mark.asyncio
async def test_eval_js_skips_less_equal():
    """x <= 5 has no assignment — no verify triggered."""
    fn = AsyncMock(return_value="true")
    wrapped = with_reflect("eval_js", fn)
    import luna_mcp.reflect.rules_runtime as rr
    orig = rr._ping_fn
    rr._ping_fn = AsyncMock(return_value="pong")
    result = await wrapped(expression="x <= 5")
    rr._ping_fn = orig
    assert "[REFLECT:" not in result


@pytest.mark.asyncio
async def test_eval_js_verifies_compound_assign_plus_equal():
    """a += 1 is an assignment — ping called, REFLECT on failure."""
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("eval_js", fn)
    import luna_mcp.reflect.rules_runtime as rr
    orig = rr._ping_fn
    rr._ping_fn = AsyncMock(return_value="")  # iframe dead → REFLECT
    result = await wrapped(expression="a += 1")
    rr._ping_fn = orig
    assert "[REFLECT:" in result


@pytest.mark.asyncio
async def test_eval_js_verifies_logical_or_assign():
    """a ||= 5 is an assignment — ping called, REFLECT on failure."""
    fn = AsyncMock(return_value="ok")
    wrapped = with_reflect("eval_js", fn)
    import luna_mcp.reflect.rules_runtime as rr
    orig = rr._ping_fn
    rr._ping_fn = AsyncMock(return_value="")  # iframe dead → REFLECT
    result = await wrapped(expression="a ||= 5")
    rr._ping_fn = orig
    assert "[REFLECT:" in result
