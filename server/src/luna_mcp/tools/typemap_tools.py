from __future__ import annotations

from . import maybe_expose


def register_typemap_tools(mcp, typemap_fn, *, exposed: set = frozenset()):
    """Typemap resolution tools. No Chrome needed."""

    async def resolve_method(class_name: str, method_name: str, signature: str = "") -> str:
        """Resolve C# method to JS name via Playworks typemap. No Chrome needed.
        signature: exact C# signature for overload resolution (optional)."""
        resolver = typemap_fn()
        if not resolver.available:
            return "error: LUNA_PLUGIN_PATH not set or typemaps not found"
        result = resolver.resolve_method(class_name, method_name, signature)
        if result is None:
            return f"not found: {class_name}.{method_name}"
        js_cls = resolver.get_js_class_name(class_name) or "?"
        return f"{class_name}.{method_name} -> {js_cls}.{result}"
    maybe_expose(mcp, resolve_method, exposed)

    async def get_class_api(class_name: str) -> str:
        """List all methods/constructors for a C# class with JS names. No Chrome needed."""
        resolver = typemap_fn()
        if not resolver.available:
            return "error: LUNA_PLUGIN_PATH not set or typemaps not found"
        return resolver.get_class_api(class_name)
    maybe_expose(mcp, get_class_api, exposed)

    return {
        "resolve_method": (resolve_method, None),
        "get_class_api": (get_class_api, None),
    }
