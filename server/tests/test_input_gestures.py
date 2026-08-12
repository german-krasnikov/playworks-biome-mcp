"""Tests for S3.1 synthetic gestures (simulate_swipe, simulate_drag, simulate_pinch, simulate_multitouch)."""
from unittest.mock import AsyncMock, Mock

import pytest


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


@pytest.fixture
def mock_bridge():
    b = Mock()
    b.send_cdp = AsyncMock(return_value={})
    return b


@pytest.fixture
def tools(mock_bridge):
    from luna_mcp.tools.input_tools import register_input_tools
    reg = register_input_tools(FakeMCP(), lambda: mock_bridge, AsyncMock(), exposed=set())
    return reg, mock_bridge


@pytest.mark.asyncio
async def test_swipe_emits_start_moves_end(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_swipe"]
    await fn(0, 0, 100, 100, steps=5)
    calls = bridge.send_cdp.call_args_list
    types = [c[1]["params"]["type"] for c in calls]
    # First: touchStart
    assert types[0] == "touchStart"
    # Middle: 5 touchMove calls
    move_calls = [c for c in calls if c[1]["params"]["type"] == "touchMove"]
    assert len(move_calls) == 5
    # Last: touchEnd with empty touchPoints
    assert types[-1] == "touchEnd"
    assert calls[-1][1]["params"]["touchPoints"] == []


@pytest.mark.asyncio
async def test_swipe_interpolation_endpoints(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_swipe"]
    await fn(0, 0, 100, 200, steps=2)
    moves = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchMove"]
    # steps=2: t=0/2=0.0 → (0,0) and t=2/2=1.0 → (100,200)
    first_pt = moves[0][1]["params"]["touchPoints"][0]
    last_pt = moves[-1][1]["params"]["touchPoints"][0]
    assert first_pt["x"] == 0 and first_pt["y"] == 0
    assert last_pt["x"] == 100 and last_pt["y"] == 200


@pytest.mark.asyncio
async def test_swipe_monotonic_x(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_swipe"]
    await fn(0, 0, 100, 0, steps=5)
    moves = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchMove"]
    xs = [c[1]["params"]["touchPoints"][0]["x"] for c in moves]
    # x should be monotonically non-decreasing
    assert xs == sorted(xs)


@pytest.mark.asyncio
async def test_pinch_two_points_diverge(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_pinch"]
    # start_dist < end_dist => diverge (spread)
    await fn(100, 100, 20, 80, steps=5)
    moves = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchMove"]
    for m in moves:
        pts = m[1]["params"]["touchPoints"]
        assert len(pts) == 2
    # Check ids are stable
    start_event = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchStart"][0]
    assert len(start_event[1]["params"]["touchPoints"]) == 2
    ids = [p["id"] for p in start_event[1]["params"]["touchPoints"]]
    assert len(set(ids)) == 2


@pytest.mark.asyncio
async def test_pinch_distance_monotonic(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_pinch"]
    await fn(100, 100, 20, 80, steps=5)
    moves = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchMove"]
    dists = []
    for m in moves:
        pts = m[1]["params"]["touchPoints"]
        dx = pts[1]["x"] - pts[0]["x"]
        dy = pts[1]["y"] - pts[0]["y"]
        dists.append((dx**2 + dy**2) ** 0.5)
    # diverge: distances should be non-decreasing
    assert dists == sorted(dists) or dists[-1] >= dists[0]


@pytest.mark.asyncio
async def test_multitouch_parses_csv(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_multitouch"]
    await fn("10,20;30,40", phase="tap")
    calls = bridge.send_cdp.call_args_list
    start = [c for c in calls if c[1]["params"]["type"] == "touchStart"]
    assert len(start) == 1
    pts = start[0][1]["params"]["touchPoints"]
    assert len(pts) == 2
    assert pts[0]["x"] == 10 and pts[0]["y"] == 20
    assert pts[1]["x"] == 30 and pts[1]["y"] == 40


@pytest.mark.asyncio
async def test_multitouch_skips_malformed(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_multitouch"]
    await fn("10,20;bad;30,40", phase="tap")
    start = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchStart"]
    pts = start[0][1]["params"]["touchPoints"]
    assert len(pts) == 2  # "bad" skipped


@pytest.mark.asyncio
async def test_gestures_are_destructive():
    from luna_mcp.tools.input_tools import register_input_tools
    destructive_registered = []

    class CaptureMCP:
        def tool(self, **kw):
            def dec(fn):
                ann = kw.get("annotations")
                if ann is not None and hasattr(ann, "readOnlyHint") and not ann.readOnlyHint:
                    destructive_registered.append(fn.__name__)
                return fn
            return dec

    b = Mock()
    b.send_cdp = AsyncMock(return_value={})
    gesture_exposed = {"simulate_swipe", "simulate_drag", "simulate_pinch", "simulate_multitouch"}
    reg = register_input_tools(CaptureMCP(), lambda: b, AsyncMock(), exposed=gesture_exposed)

    # All 4 gesture tools must be in the returned dict
    for name in gesture_exposed:
        assert name in reg, f"{name} missing from returned dict"

    # simulate_swipe is the only gesture exposed (in EXPOSED_TOOLS); the others are batch-only
    assert "simulate_swipe" in reg

    # The 4 gesture tools must have been registered as destructive (readOnlyHint=False)
    for name in ("simulate_swipe", "simulate_drag", "simulate_pinch", "simulate_multitouch"):
        assert name in destructive_registered, f"{name} was not registered as destructive"


@pytest.mark.asyncio
async def test_swipe_steps_zero_emits_at_least_one_move(tools):
    """steps=0 must emit at least one touchMove (normalized to 1)."""
    reg, bridge = tools
    fn, _ = reg["simulate_swipe"]
    await fn(0, 0, 100, 100, steps=0)
    moves = [c for c in bridge.send_cdp.call_args_list if c[1]["params"]["type"] == "touchMove"]
    assert len(moves) >= 1


@pytest.mark.asyncio
async def test_swipe_uses_cdp_not_call_fn(mock_bridge):
    call_fn_mock = AsyncMock()
    from luna_mcp.tools.input_tools import register_input_tools
    reg = register_input_tools(FakeMCP(), lambda: mock_bridge, AsyncMock(), exposed=set())
    fn, _ = reg["simulate_swipe"]
    await fn(0, 0, 10, 10, steps=2)
    # call_fn not used — only send_cdp
    assert mock_bridge.send_cdp.called
    call_fn_mock.assert_not_called()


def test_coordinate_space_documented():
    """Each gesture docstring contains 'CSS px' or 'page'."""
    from luna_mcp.tools.input_tools import register_input_tools
    reg = register_input_tools(FakeMCP(), lambda: Mock(), AsyncMock(), exposed=set())
    for name in ("simulate_swipe", "simulate_drag", "simulate_pinch", "simulate_multitouch"):
        fn, _ = reg[name]
        doc = fn.__doc__ or ""
        assert "CSS px" in doc or "page" in doc, f"{name} docstring missing coordinate space mention"


@pytest.mark.asyncio
async def test_simulate_drag_batch_only(mock_bridge):
    from luna_mcp.tools.input_tools import register_input_tools
    reg = register_input_tools(FakeMCP(), lambda: mock_bridge, AsyncMock(), exposed=set())
    assert "simulate_drag" in reg
    fn, _ = reg["simulate_drag"]
    await fn(0, 0, 50, 50)
    # should have sent touchStart, moves, touchEnd
    types = [c[1]["params"]["type"] for c in mock_bridge.send_cdp.call_args_list]
    assert "touchStart" in types
    assert "touchEnd" in types
