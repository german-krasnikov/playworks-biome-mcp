from ..hierarchy_distiller.distiller import distill_tier1, format_stats
from . import maybe_expose

# Auto-distill when hierarchy response exceeds this many characters
HIERARCHY_SIZE_THRESHOLD = 3000


def register_scene_tools(mcp, call_fn, *, exposed: set = frozenset()):
    """Register scene inspection tools. Returns {name: (fn, params)} for batch."""

    async def get_hierarchy(depth: int = 3, root: str = "") -> str:
        """Read the Luna scene hierarchy as a text tree. depth controls how many levels deep; root filters to a subtree by path. Use first to discover object paths before calling get_component or get_object_detail."""
        result = await call_fn("getHierarchy", depth, root)
        if (
            not result.startswith("error:")
            and len(result) > HIERARCHY_SIZE_THRESHOLD
        ):
            stats = distill_tier1(result)
            summary = format_stats(stats)
            return f"[DISTILLED]\n{summary}"
        return result
    maybe_expose(mcp, get_hierarchy, exposed)

    async def get_component(path: str, component_type: str) -> str:
        """Read all properties of a specific component as key-value text. Use get_components_list first to discover available types. For a full dump of all components at once, use get_object_detail instead."""
        return await call_fn("getComponent", path, component_type)
    maybe_expose(mcp, get_component, exposed)

    async def get_components_list(path: str) -> str:
        """List component types attached to a scene object."""
        return await call_fn("getComponents", path)
    maybe_expose(mcp, get_components_list, exposed)

    async def get_object_detail(path: str) -> str:
        """Full dump of a GameObject: transform + all components with properties. Use for comprehensive one-shot inspection. For a single component, use get_component instead (smaller response)."""
        return await call_fn("getObjectDetail", path)
    maybe_expose(mcp, get_object_detail, exposed)

    async def find_objects(query: str) -> str:
        """Find scene objects by name substring. Returns matching paths, one per line. Use when you know part of an object's name but not its full hierarchy path. For filtering by component type, use find_objects_by_component."""
        return await call_fn("findObjects", query)
    maybe_expose(mcp, find_objects, exposed)

    async def find_objects_by_component(component_type: str) -> str:
        """Find all GameObjects that have a specific component type attached. Returns paths, one per line. Use instead of find_objects when filtering by component rather than name."""
        return await call_fn("findByComponent", component_type)
    maybe_expose(mcp, find_objects_by_component, exposed)

    return {
        "get_hierarchy": (get_hierarchy, None),
        "get_component": (get_component, None),
        "get_components_list": (get_components_list, None),
        "get_object_detail": (get_object_detail, None),
        "find_objects": (find_objects, None),
        "find_objects_by_component": (find_objects_by_component, None),
    }
