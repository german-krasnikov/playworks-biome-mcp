"""Tests for SchemaGuard, SchemaCache, BatchPathCache, and middleware."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LUNA_MCP_VALIDATE", "1")


# ── imports (will fail until modules exist) ──────────────────────────────────

from luna_mcp.middleware import wrap_with_guard
from luna_mcp.schema_cache import BatchPathCache, SchemaCache
from luna_mcp.schema_guard import SchemaGuard

# ── fixtures ─────────────────────────────────────────────────────────────────

def make_guard(typemap_known=None, runtime_call=None):
    """Create SchemaGuard with mock dependencies."""
    cache = SchemaCache()
    tm = MagicMock()
    if typemap_known is not None:
        tm.is_loaded.return_value = True
        def get_js(name):
            return name if name in typemap_known else None
        tm.get_js_class_name.side_effect = get_js
        tm.known_classes.return_value = list(typemap_known)
    else:
        tm.is_loaded.return_value = False
    call_fn = runtime_call or AsyncMock(return_value="ok")
    return SchemaGuard(cache, tm, call_fn)


# ── L1: shape validation (sync rules) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_l1_blocks_set_transform_with_invalid_prop():
    """set_transform with prop='enabled' should block and suggest 'position'."""
    guard = make_guard()
    result = await guard.validate("set_transform", {
        "path": "/Root/Player",
        "prop": "enabled",
        "x": 1.0, "y": 0.0, "z": 0.0
    }, None)
    assert result is not None
    assert "[INVALID" in result
    assert "enabled" in result
    assert "BYPASS" in result


@pytest.mark.asyncio
async def test_l1_blocks_path_without_slash_prefix():
    """set_property/get_component path must start with '/'."""
    guard = make_guard()
    result = await guard.validate("set_property", {
        "path": "Root/Player",
        "component_type": "Transform",
        "prop": "position",
        "value": "1"
    }, None)
    assert result is not None
    assert "[INVALID" in result
    assert "path" in result.lower()


@pytest.mark.asyncio
async def test_l1_blocks_missing_required_arg():
    """set_property without 'prop' key should block instantly."""
    guard = make_guard()
    result = await guard.validate("set_property", {
        "path": "/Root/Player",
        "component_type": "Transform",
        # 'prop' missing
    }, None)
    assert result is not None
    assert "[INVALID" in result


# ── L2: typemap checks ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l2_typemap_blocks_typo():
    """component_type='Trnsform' → suggests 'Transform' with lev=1."""
    known = {"Transform", "Renderer", "Rigidbody"}
    guard = make_guard(typemap_known=known)
    result = await guard.validate("set_property", {
        "path": "/Root",
        "component_type": "Trnsform",
        "prop": "enabled",
        "value": "true"
    }, None)
    assert result is not None
    assert "[INVALID" in result
    assert "Transform" in result
    assert "lev=1" in result


@pytest.mark.asyncio
async def test_l2_typemap_passes_known_class():
    """component_type='Transform' (exact match) should pass."""
    known = {"Transform", "Renderer"}
    guard = make_guard(typemap_known=known)
    result = await guard.validate("set_property", {
        "path": "/Root",
        "component_type": "Transform",
        "prop": "enabled",
        "value": "true"
    }, None)
    assert result is None


@pytest.mark.asyncio
async def test_l2_prop_typo_caught():
    """prop='enabld' on known component → blocks with 'enabled' suggestion."""
    cache = SchemaCache()
    cache.put("Transform", frozenset(["enabled", "position", "rotation", "scale"]))
    tm = MagicMock()
    tm.is_loaded.return_value = True
    tm.get_js_class_name.return_value = "Transform"
    tm.known_classes.return_value = ["Transform"]
    guard = SchemaGuard(cache, tm, AsyncMock(return_value="ok"))
    result = await guard.validate("set_property", {
        "path": "/Root",
        "component_type": "Transform",
        "prop": "enabld",
        "value": "true"
    }, None)
    assert result is not None
    assert "enabled" in result
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_l2_prop_unknown_no_close_match_passes():
    """prop='xyz_very_different_prop' lev>2 → pass (avoid false positives)."""
    cache = SchemaCache()
    cache.put("Transform", frozenset(["enabled", "position", "rotation"]))
    tm = MagicMock()
    tm.is_loaded.return_value = True
    tm.get_js_class_name.return_value = "Transform"
    tm.known_classes.return_value = ["Transform"]
    guard = SchemaGuard(cache, tm, AsyncMock(return_value="ok"))
    result = await guard.validate("set_property", {
        "path": "/Root",
        "component_type": "Transform",
        "prop": "xyz_very_different_prop",
        "value": "1"
    }, None)
    assert result is None


# ── bypass / fail-open ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_validate_bypass():
    """_no_validate=True in kw → wrap_with_guard skips validation entirely."""
    guard = make_guard()
    inner = AsyncMock(return_value="result")

    class Holder:
        def get(self): return None

    wrapped, _ = wrap_with_guard("set_property", inner, {}, guard, Holder())
    result = await wrapped(path="bad_path", _no_validate=True)
    assert result == "result"
    inner.assert_called_once_with(path="bad_path")


@pytest.mark.asyncio
async def test_fail_open_on_exception():
    """If SchemaGuard.validate raises, wrapped fn still executes."""
    cache = SchemaCache()
    tm = MagicMock()
    tm.is_loaded.return_value = True
    tm.get_js_class_name.side_effect = RuntimeError("unexpected crash")
    tm.known_classes.return_value = []
    guard = SchemaGuard(cache, tm, AsyncMock(return_value="ok"))
    inner = AsyncMock(return_value="success")

    class Holder:
        def get(self): return None

    wrapped, _ = wrap_with_guard("set_property", inner, {}, guard, Holder())
    result = await wrapped(path="/Root", component_type="Transform", prop="p", value="1")
    assert result == "success"


# ── batch pre-flight ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_pre_flight_aborts_at_first_invalid_step():
    """Batch dry_run=True aborts at first invalid step, no tools executed."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY, execute_batch, register_batch_tool

    original = dict(_TOOL_REGISTRY)
    try:
        handler = AsyncMock(return_value="ok")
        register_batch_tool("ping", handler, {})

        # set_transform with invalid prop — should abort in dry_run
        from luna_mcp.schema_guard import _GUARD
        if _GUARD is None:
            pytest.skip("GUARD not wired in server; testing pre-flight separately")

        result = await execute_batch(
            "set_transform path=/Root prop=enabled x=1 y=0 z=0\nping",
            dry_run=True
        )
        assert "ABORTED" in result or "INVALID" in result
        handler.assert_not_called()
    finally:
        _TOOL_REGISTRY.clear()
        _TOOL_REGISTRY.update(original)


# ── SchemaCache ───────────────────────────────────────────────────────────────

def test_path_cache_invalidated_after_destroy():
    """BatchPathCache clears all entries on invalidate."""
    pc = BatchPathCache()
    pc["/Root/A"] = True
    pc["/Root/B"] = False
    pc.invalidate()
    assert len(pc) == 0


def test_cache_invalidate_on_reconnect():
    """SchemaCache.invalidate_all() clears all cached props."""
    cache = SchemaCache()
    cache.put("Transform", frozenset(["position", "rotation"]))
    cache.put("Renderer", frozenset(["enabled"]))
    cache.invalidate_all()
    assert cache.get("Transform") is None
    assert cache.get("Renderer") is None


# ── dry_run ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_returns_ok_without_cdp_eval():
    """execute_batch dry_run=True with valid commands returns OK message."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY, execute_batch, register_batch_tool

    original = dict(_TOOL_REGISTRY)
    try:
        handler = AsyncMock(return_value="pong")
        register_batch_tool("ping", handler, {})
        result = await execute_batch("ping\nping", dry_run=True)
        assert "DRY-RUN OK" in result or "dry" in result.lower()
        handler.assert_not_called()
    finally:
        _TOOL_REGISTRY.clear()
        _TOOL_REGISTRY.update(original)


# ── C1: direct MCP call validated by guard ────────────────────────────────────

@pytest.mark.asyncio
async def test_direct_set_property_validated_by_guard():
    """wrap_with_guard applied to direct MCP call blocks invalid args (C1)."""
    guard = make_guard()
    inner = AsyncMock(return_value="ok")

    class NullHolder:
        def get(self): return None

    wrapped, _ = wrap_with_guard("set_property", inner, {}, guard, NullHolder())
    # path without leading slash — guard L1 must block
    result = await wrapped(
        path="Root/Player",
        component_type="Transform",
        prop="position",
        value="1",
    )
    assert "[INVALID" in result
    inner.assert_not_called()


@pytest.mark.asyncio
async def test_set_property_guarded_via_composition_stack():
    """SchemaGuard validation is applied via composition stack _guarded wrapper, not inside modify_tools."""
    from luna_mcp.tools.modify_tools import register_modify_tools

    call_fn = AsyncMock(return_value="ok")
    mock_mcp = MagicMock()
    mock_mcp.tool = MagicMock(return_value=lambda f: f)
    tools = register_modify_tools(mock_mcp, call_fn, exposed=set())
    set_prop_fn = tools["set_property"][0]

    # Without composition stack, modify_tools passes through to call_fn directly
    result = await set_prop_fn(path="Root/Player", component_type="Transform", prop="position", value="1")
    assert result == "ok"
    call_fn.assert_called_once()
