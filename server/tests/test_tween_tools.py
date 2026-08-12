"""Tests for S3.2 DOTween inventory and control tools."""
import pathlib

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


def make_call_fn(return_values: dict):
    async def call_fn(method, *args):
        return return_values.get(method, "")
    return call_fn


# --- tween_inventory ---

@pytest.mark.asyncio
async def test_inventory_passthrough():
    tween_data = "0 | dur=1.0 | pos=0.5 | loops=0 | playing=True | complete=False | target=Cube"
    call_fn = make_call_fn({"tweenList": tween_data})
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_inventory"]
    result = await fn()
    assert result == tween_data


@pytest.mark.asyncio
async def test_inventory_absent():
    call_fn = make_call_fn({"tweenList": "DOTween not present in this build"})
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_inventory"]
    result = await fn()
    assert "DOTween not present in this build" in result


# --- tween_control ---

@pytest.mark.asyncio
async def test_control_pause():
    called = []
    async def call_fn(method, *args):
        called.append((method, args))
        return "paused all"
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_control"]
    result = await fn("pause")
    assert ("tweenControl", ("pause",)) in called
    assert result == "paused all"


@pytest.mark.asyncio
async def test_control_invalid():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        return ""
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_control"]
    result = await fn("fly")
    assert "INVALID" in result
    assert not called


def test_control_is_destructive():
    import inspect

    from luna_mcp.tools.tween_tools import register_tween_tools
    src = inspect.getsource(register_tween_tools)
    # tween_control must be registered with read_only=False
    assert "read_only=False" in src


# --- tween_health ---

@pytest.mark.asyncio
async def test_health_two_sample_stuck():
    """Same position across two samples → STUCK idx=<i>."""
    snap = "3 | dur=1.0 | pos=0.25 | loops=0 | playing=True | complete=False | target=?"
    call_fn = make_call_fn({"tweenList": snap})
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_health"]
    result = await fn(interval_ms=0)
    assert "STUCK" in result
    assert "idx=3" in result


@pytest.mark.asyncio
async def test_health_two_sample_ok():
    """Different positions across two samples → OK."""
    responses = ["3 | dur=1.0 | pos=0.25 | loops=0 | playing=True | complete=False | target=?",
                 "3 | dur=1.0 | pos=0.50 | loops=0 | playing=True | complete=False | target=?"]
    call_count = [0]
    async def call_fn(method, *args):
        if method == "tweenList":
            val = responses[min(call_count[0], 1)]
            call_count[0] += 1
            return val
        return ""
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_health"]
    result = await fn(interval_ms=0)
    assert "OK" in result or "STUCK" not in result


@pytest.mark.asyncio
async def test_health_completed_not_stuck():
    """Completed tween (playing=False) at identical pos must NOT be flagged STUCK."""
    snap = "2 | dur=1.0 | pos=1.0 | loops=0 | playing=False | complete=True | target=Cube"
    call_fn = make_call_fn({"tweenList": snap})
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_health"]
    result = await fn(interval_ms=0)
    assert "STUCK" not in result


@pytest.mark.asyncio
async def test_health_infinite_loop():
    """loops=-1 and playing=True → INFINITE flag."""
    snap = "0 | dur=2.0 | pos=0.1 | loops=-1 | playing=True | complete=False | target=?"
    call_fn = make_call_fn({"tweenList": snap})
    from luna_mcp.tools.tween_tools import register_tween_tools
    reg = register_tween_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["tween_health"]
    result = await fn(interval_ms=0)
    assert "INFINITE" in result


# --- JS presence ---

def test_js_tweenList_present():
    src = JS_PATH.read_text()
    assert "tweenList:" in src


def test_js_tweenControl_present():
    src = JS_PATH.read_text()
    assert "tweenControl:" in src


def test_js_dotween_not_present_msg():
    src = JS_PATH.read_text()
    assert "DOTween not present in this build" in src


def test_js_dotween_guard():
    src = JS_PATH.read_text()
    assert "DG.Tweening.Core.TweenManager" in src
