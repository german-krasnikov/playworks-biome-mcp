from __future__ import annotations

from . import maybe_expose


def _parse_value(value: str):
    """Parse string to number/bool/string for JS."""
    if value.lower() == "true": return True
    if value.lower() == "false": return False
    try: return float(value) if '.' in value else int(value)
    except ValueError: return value


def register_modify_tools(mcp, call_fn, *, exposed: set = frozenset()):
    """Register property/transform mutation tools. Returns {name: (fn, params)} for batch."""

    async def set_property(path: str, component_type: str, prop: str, value: str) -> str:
        """Set a property on a component. value is auto-parsed: '3.14' → float, 'true' → bool, else string. Use get_component first to confirm exact property names. For transform (position/rotation/scale) use set_transform instead."""
        return await call_fn("setProperty", path, component_type, prop, _parse_value(value))
    maybe_expose(mcp, set_property, exposed, read_only=False)

    async def set_transform(path: str, prop: str, x: float, y: float, z: float) -> str:
        """Set a Vector3 transform property (position, rotation, or scale) by world-space xyz. Use instead of set_property for transforms — it handles Vector3 correctly."""
        return await call_fn("setTransform", path, prop, x, y, z)
    maybe_expose(mcp, set_transform, exposed, read_only=False)

    return {
        "set_property": (set_property, None),
        "set_transform": (set_transform, None),
    }
