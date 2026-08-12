"""Testable helpers extracted from server.py wrapper logic."""
from typing import Optional

_LESSON_INJECT_CMDS = frozenset({"set_property", "set_transform", "get_component", "get_object_detail"})


def _maybe_inject_lesson(name: str, kw: dict, store) -> Optional[str]:
    cls = kw.get("component_type")
    if not cls:
        return None
    from luna_mcp.lessons.matcher import find_lesson_for_class
    return find_lesson_for_class(store, name, cls, kw.get("prop", ""))


