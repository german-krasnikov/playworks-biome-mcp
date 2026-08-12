"""S3.4 Physics forensics tools: inspect bodies, query, contact pairs."""
from ..physics_detective.backend_detector import BackendInfo
from . import maybe_expose

_VALID_KINDS = {"raycast2d", "overlap2d", "raycast3d"}


def register_physics_forensics_tools(mcp, call_fn, *, exposed: set = frozenset()):
    """Register physics forensics tools. Returns {name: (fn, params)} for batch."""

    async def inspect_bodies(path: str = "", max_n: int = 40) -> str:
        """Inspect active physics bodies. Reuses physicsProbe to detect backend."""
        raw = await call_fn("physicsProbe")
        info = BackendInfo(str(raw or ""))
        if not info.active_backends():
            return "no physics in scene"
        if info.goblin or info.unified:
            return await call_fn("rigidbodyDump", path)
        if info.verlet or info.baked:
            return await call_fn("listBodies2d", max_n)
        return "no physics in scene"
    maybe_expose(mcp, inspect_bodies, exposed, read_only=True)

    async def physics_query(kind: str, a: float, b: float, c: float = 0, d: float = 0, dist: float = 1e9) -> str:
        """Query physics: kind in {raycast2d, overlap2d, raycast3d}."""
        if kind not in _VALID_KINDS:
            return "[INVALID: kind must be raycast2d|overlap2d|raycast3d]"
        if kind == "raycast2d":
            return await call_fn("raycast2d", a, b, c, d, dist)
        if kind == "overlap2d":
            return await call_fn("overlapPoint2d", a, b)
        if kind == "raycast3d":
            return await call_fn("raycast", a, b)
        return "[INVALID: kind must be raycast2d|overlap2d|raycast3d]"
    maybe_expose(mcp, physics_query, exposed, read_only=True)

    async def contact_pairs() -> str:
        """Return contact pairs from the active physics backend."""
        return await call_fn("contactPairs")
    maybe_expose(mcp, contact_pairs, exposed, read_only=True)

    return {
        "inspect_bodies": (inspect_bodies, None),
        "physics_query": (physics_query, None),
        "contact_pairs": (contact_pairs, None),
    }
