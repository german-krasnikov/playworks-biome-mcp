import asyncio

from . import maybe_expose

TOUCH_ID_DEFAULT = 0


def _interp(a: float, b: float, t: float) -> int:
    return round(a + (b - a) * t)


def register_input_tools(mcp, bridge_getter, ensure_fn, *, exposed: set = frozenset()):
    """Register input simulation tools. Returns {name: (fn, params)} for batch."""

    async def simulate_click(x: int, y: int) -> str:
        """Click at (x,y) via CDP Input.dispatchMouseEvent."""
        await ensure_fn()
        b = bridge_getter()
        await b.send_cdp("Input.dispatchMouseEvent", params={"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await b.send_cdp("Input.dispatchMouseEvent", params={"type": "mouseReleased", "x": x, "y": y, "button": "left"})
        return f"clicked ({x}, {y})"
    maybe_expose(mcp, simulate_click, exposed)

    async def simulate_touch(x: int, y: int) -> str:
        """Touch at (x,y) via CDP Input.dispatchTouchEvent."""
        await ensure_fn()
        b = bridge_getter()
        await b.send_cdp("Input.dispatchTouchEvent", params={"type": "touchStart", "touchPoints": [{"id": TOUCH_ID_DEFAULT, "x": x, "y": y}]})
        await b.send_cdp("Input.dispatchTouchEvent", params={"type": "touchEnd", "touchPoints": []})
        return f"touched ({x}, {y})"
    maybe_expose(mcp, simulate_touch, exposed)

    async def simulate_key(key: str, modifiers: int = 0) -> str:
        """Press key via CDP Input.dispatchKeyEvent. modifiers: 1=Alt 2=Ctrl 4=Meta 8=Shift."""
        await ensure_fn()
        b = bridge_getter()
        await b.send_cdp("Input.dispatchKeyEvent", params={"type": "keyDown", "key": key, "modifiers": modifiers})
        await b.send_cdp("Input.dispatchKeyEvent", params={"type": "keyUp", "key": key, "modifiers": modifiers})
        return f"key: {key}"
    maybe_expose(mcp, simulate_key, exposed)

    async def simulate_swipe(x1: int, y1: int, x2: int, y2: int, steps: int = 10, duration_ms: int = 200) -> str:
        """Swipe from (x1,y1) to (x2,y2) via CDP Input.dispatchTouchEvent. Coords are page CSS px."""
        steps = max(steps, 1)
        await ensure_fn()
        b = bridge_getter()
        tid = TOUCH_ID_DEFAULT
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchStart",
            "touchPoints": [{"id": tid, "x": x1, "y": y1}],
        })
        for i in range(steps):
            t = i / (steps - 1) if steps > 1 else 0.0
            mx = _interp(x1, x2, t)
            my = _interp(y1, y2, t)
            await b.send_cdp("Input.dispatchTouchEvent", params={
                "type": "touchMove",
                "touchPoints": [{"id": tid, "x": mx, "y": my}],
            })
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchEnd",
            "touchPoints": [],
        })
        return f"swipe ({x1},{y1})->({x2},{y2}) steps={steps}"
    maybe_expose(mcp, simulate_swipe, exposed, read_only=False)

    async def simulate_drag(x1: int, y1: int, x2: int, y2: int, steps: int = 10, hold_ms: int = 0) -> str:
        """Drag from (x1,y1) to (x2,y2) via CDP Input.dispatchTouchEvent. Coords are page CSS px."""
        steps = max(steps, 1)
        await ensure_fn()
        b = bridge_getter()
        tid = TOUCH_ID_DEFAULT
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchStart",
            "touchPoints": [{"id": tid, "x": x1, "y": y1}],
        })
        if hold_ms > 0:
            await asyncio.sleep(hold_ms / 1000)
        for i in range(steps):
            t = i / (steps - 1) if steps > 1 else 0.0
            mx = _interp(x1, x2, t)
            my = _interp(y1, y2, t)
            await b.send_cdp("Input.dispatchTouchEvent", params={
                "type": "touchMove",
                "touchPoints": [{"id": tid, "x": mx, "y": my}],
            })
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchEnd",
            "touchPoints": [],
        })
        return f"drag ({x1},{y1})->({x2},{y2}) steps={steps}"
    maybe_expose(mcp, simulate_drag, exposed, read_only=False)

    async def simulate_pinch(cx: int, cy: int, start_dist: int, end_dist: int, steps: int = 10) -> str:
        """Pinch/spread from start_dist to end_dist around center (cx,cy). Coords are page CSS px."""
        steps = max(steps, 1)
        await ensure_fn()
        b = bridge_getter()
        id0, id1 = 0, 1
        half0 = start_dist // 2
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchStart",
            "touchPoints": [
                {"id": id0, "x": cx - half0, "y": cy},
                {"id": id1, "x": cx + half0, "y": cy},
            ],
        })
        for i in range(steps):
            t = i / (steps - 1) if steps > 1 else 0.0
            dist = _interp(start_dist, end_dist, t)
            half = dist // 2
            await b.send_cdp("Input.dispatchTouchEvent", params={
                "type": "touchMove",
                "touchPoints": [
                    {"id": id0, "x": cx - half, "y": cy},
                    {"id": id1, "x": cx + half, "y": cy},
                ],
            })
        await b.send_cdp("Input.dispatchTouchEvent", params={
            "type": "touchEnd",
            "touchPoints": [],
        })
        return f"pinch cx={cx},cy={cy} {start_dist}->{end_dist}"
    maybe_expose(mcp, simulate_pinch, exposed, read_only=False)

    async def simulate_multitouch(points_csv: str, phase: str = "tap") -> str:
        """Multi-touch using 'x,y;x,y' CSV format. Coords are page CSS px. Malformed tokens skipped."""
        await ensure_fn()
        b = bridge_getter()
        pts = []
        for tok in points_csv.split(";"):
            parts = tok.strip().split(",")
            if len(parts) != 2:
                continue
            try:
                pts.append({"id": len(pts), "x": int(parts[0]), "y": int(parts[1])})
            except ValueError:
                continue
        if not pts:
            return "no valid touch points"
        await b.send_cdp("Input.dispatchTouchEvent", params={"type": "touchStart", "touchPoints": pts})
        await b.send_cdp("Input.dispatchTouchEvent", params={"type": "touchEnd", "touchPoints": []})
        return f"multitouch phase={phase} points={len(pts)}"
    maybe_expose(mcp, simulate_multitouch, exposed, read_only=False)

    return {
        "simulate_click": (simulate_click, None),
        "simulate_touch": (simulate_touch, None),
        "simulate_key": (simulate_key, None),
        "simulate_swipe": (simulate_swipe, None),
        "simulate_drag": (simulate_drag, None),
        "simulate_pinch": (simulate_pinch, None),
        "simulate_multitouch": (simulate_multitouch, None),
    }
