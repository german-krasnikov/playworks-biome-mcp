import json

from . import maybe_expose


def register_state_tools(mcp, call_fn, send_fn, *, exposed: set = frozenset()):
    """Register state management tools. Returns {name: (fn, params)} for batch."""

    async def watch_property(path: str, component: str, prop: str, interval_ms: int = 100, count: int = 10) -> str:
        """Poll a property N times at interval_ms. Returns timestamped value history."""
        timeout = max(30.0, (interval_ms * count) / 1000.0 + 5.0)
        args = ", ".join(json.dumps(a) for a in [path, component, prop, interval_ms, count])
        expr = f"document.querySelector('iframe').contentWindow.__luna_mcp.watchProperty({args})"
        return await send_fn(expr, timeout=timeout)
    maybe_expose(mcp, watch_property, exposed)

    async def snapshot_state(name: str, path: str) -> str:
        """Save transform + serializable component fields of object to named snapshot."""
        return await call_fn("snapshotState", name, path)
    maybe_expose(mcp, snapshot_state, exposed)

    async def restore_state(name: str) -> str:
        """Restore object state from named snapshot."""
        return await call_fn("restoreState", name)
    maybe_expose(mcp, restore_state, exposed)

    return {
        "watch_property": (watch_property, None),
        "snapshot_state": (snapshot_state, None),
        "restore_state": (restore_state, None),
    }
