"""Tests for composition.py — 6-layer composition stack."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---- helpers ----

async def _identity(*args, **kw):
    return "ok"


async def _raise_fn(*args, **kw):
    raise ValueError("oops")


# ---- _guarded ----

@pytest.mark.asyncio
async def test_guarded_passes_when_guard_none():
    from luna_mcp.composition import _guarded
    fn = _guarded("test_tool", _identity, guard_module=MagicMock(_GUARD=None))
    assert await fn(x=1) == "ok"


@pytest.mark.asyncio
async def test_guarded_blocks_when_guard_returns_message():
    from luna_mcp.composition import _guarded
    guard = MagicMock()
    guard.validate = AsyncMock(return_value="blocked: bad schema")
    mod = MagicMock(_GUARD=guard)
    fn = _guarded("set_property", _identity, guard_module=mod)
    result = await fn(x=1)
    assert result == "blocked: bad schema"


@pytest.mark.asyncio
async def test_guarded_skips_validate_with_no_validate_flag():
    from luna_mcp.composition import _guarded
    guard = MagicMock()
    guard.validate = AsyncMock(return_value="blocked")
    mod = MagicMock(_GUARD=guard)
    fn = _guarded("set_property", _identity, guard_module=mod)
    result = await fn(_no_validate=True)
    # Should call _identity, not guard
    assert result == "ok"
    guard.validate.assert_not_called()


# ---- _degraded ----

@pytest.mark.asyncio
async def test_degraded_short_circuits_when_degradation_returns():
    from luna_mcp.composition import _degraded
    deg_fn = MagicMock(return_value="DEGRADED:chrome — restart Chrome")
    fn = _degraded("get_hierarchy", _identity, degradation_fn=deg_fn)
    result = await fn()
    assert result == "DEGRADED:chrome — restart Chrome"
    deg_fn.assert_called_once_with({})


@pytest.mark.asyncio
async def test_degraded_passes_through_when_none():
    from luna_mcp.composition import _degraded
    deg_fn = MagicMock(return_value=None)
    fn = _degraded("get_hierarchy", _identity, degradation_fn=deg_fn)
    result = await fn()
    assert result == "ok"


@pytest.mark.asyncio
async def test_degraded_no_op_when_degradation_fn_is_none():
    from luna_mcp.composition import _degraded
    fn = _degraded("get_hierarchy", _identity, degradation_fn=None)
    result = await fn()
    assert result == "ok"


# ---- _hinted ----

@pytest.mark.asyncio
async def test_hinted_returns_skipped_unchanged():
    from luna_mcp.composition import _hinted
    async def skipped_fn(*a, **kw):
        return "[skipped get_hierarchy: budget exceeded]"

    lessons = MagicMock()
    hinter = MagicMock()
    fn = _hinted("get_hierarchy", skipped_fn, get_lessons_store=lambda: lessons,
                 hinter=hinter, lesson_inject_cmds={"get_hierarchy"})
    result = await fn()
    assert result == "[skipped get_hierarchy: budget exceeded]"
    hinter.observe.assert_not_called()


@pytest.mark.asyncio
async def test_hinted_injects_lesson_when_available():
    from luna_mcp.composition import _hinted

    async def tool_fn(*a, **kw):
        return "result text"

    lessons = MagicMock()
    lessons.lookup = MagicMock(return_value=None)
    hinter = MagicMock()
    hinter.observe = MagicMock(return_value=None)

    with patch("luna_mcp.composition._maybe_inject_lesson", return_value="LESSON: use X") as mock_lesson:
        fn = _hinted("get_component", tool_fn, get_lessons_store=lambda: lessons,
                     hinter=hinter, lesson_inject_cmds={"get_component"})
        result = await fn(path="Root")

    assert "LESSON: use X" in result
    assert "result text" in result


@pytest.mark.asyncio
async def test_hinted_appends_hint_when_hinter_returns():
    from luna_mcp.composition import _hinted

    async def tool_fn(*a, **kw):
        return "result"

    hinter = MagicMock()
    hinter.observe = MagicMock(return_value="[hint: use batch]")

    with patch("luna_mcp.composition._maybe_inject_lesson", return_value=None):
        fn = _hinted("eval_js", tool_fn, get_lessons_store=lambda: None,
                     hinter=hinter, lesson_inject_cmds=set())
        result = await fn()

    assert "[hint: use batch]" in result


# ---- _recorded ----

@pytest.mark.asyncio
async def test_recorded_logs_when_recorder_active(monkeypatch):
    from luna_mcp.composition import _recorded

    recorder = MagicMock()
    recorder.active = True
    recorder.log = MagicMock()

    with patch.dict("os.environ", {"LUNA_RECORD": "1"}):
        fn = _recorded("eval_js", _identity, recorder=recorder)
        result = await fn(expr="1+1")

    assert result == "ok"
    recorder.log.assert_called_once()


@pytest.mark.asyncio
async def test_recorded_skips_when_record_env_off():
    from luna_mcp.composition import _recorded

    recorder = MagicMock()
    recorder.active = True

    with patch.dict("os.environ", {"LUNA_RECORD": "0"}):
        fn = _recorded("eval_js", _identity, recorder=recorder)
        await fn(expr="1+1")

    recorder.log.assert_not_called()


# ---- apply_composition ----

@pytest.mark.asyncio
async def test_apply_composition_wraps_all_tools():
    from luna_mcp.composition import apply_composition

    async def tool_a(**kw): return "a"
    async def tool_b(**kw): return "b"

    all_tools = {
        "tool_a": (tool_a, {"x": str}),
        "tool_b": (tool_b, {"y": int}),
    }

    recorder = MagicMock()
    recorder.active = False

    budget_router = MagicMock()
    budget_router.decide = MagicMock(return_value=MagicMock(action="run", hint=None, target=None))

    budget_tracker = MagicMock()
    budget_tracker.record = MagicMock()

    import luna_mcp.schema_guard as _sg
    _sg._GUARD = None

    registry = apply_composition(
        all_tools,
        budget_router=budget_router,
        budget_tracker=budget_tracker,
        get_metrics=lambda: None,
        get_calibrator=lambda: None,
        get_watchdog=lambda: None,
        recorder=recorder,
        get_degradation=lambda: None,
        get_lessons_store=lambda: None,
        hinter=MagicMock(observe=MagicMock(return_value=None)),
        guard_module=_sg,
        reflect_fn=None,
        lesson_inject_cmds=set(),
        reflect_cmds=set(),
        budget_own={"tool_b"},
        mutation_cmds=set(),
        recorder_skip=set(),
        hinter_skip=set(),
    )

    assert "tool_a" in registry
    assert "tool_b" in registry
    fn_a, params_a = registry["tool_a"]
    result = await fn_a(x="hi")
    assert result == "a"
