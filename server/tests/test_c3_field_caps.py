"""C3 tests: field-capped readComponentFields + self-compressing get_hierarchy.

RED phase — all tests must fail before implementation.
"""
from __future__ import annotations

import pytest

# ── C3(a): JS readComponentFields caps ──────────────────────────────────────
# We test the JS-side logic by checking the constants exported from a Python
# module that mirrors the caps, and by testing the Python-side helper that
# formats the "+K more" marker.

def test_js_field_cap_constant_exists():
    """JS must export FIELD_CAP and VALUE_CAP as readable constants."""
    from luna_mcp.js_field_caps import FIELD_CAP, VALUE_CAP
    assert isinstance(FIELD_CAP, int) and FIELD_CAP > 0
    assert isinstance(VALUE_CAP, int) and VALUE_CAP > 0


def test_js_field_cap_reasonable_defaults():
    """FIELD_CAP <= 30 and VALUE_CAP <= 200 to stay token-minimal."""
    from luna_mcp.js_field_caps import FIELD_CAP, VALUE_CAP
    assert FIELD_CAP <= 30
    assert VALUE_CAP <= 200


def test_truncate_value_short_unchanged():
    """Values <= VALUE_CAP are returned as-is."""
    from luna_mcp.js_field_caps import VALUE_CAP, truncate_value
    short = "x" * (VALUE_CAP - 1)
    assert truncate_value(short) == short


def test_truncate_value_long_gets_ellipsis():
    """Values > VALUE_CAP get an ellipsis suffix."""
    from luna_mcp.js_field_caps import VALUE_CAP, truncate_value
    long_val = "x" * (VALUE_CAP + 50)
    result = truncate_value(long_val)
    assert result.endswith("…")
    assert len(result) <= VALUE_CAP + 5  # small slack for ellipsis


def test_more_marker_format():
    """format_more_marker returns '+K more' string."""
    from luna_mcp.js_field_caps import format_more_marker
    assert format_more_marker(5) == "+5 more fields"
    assert format_more_marker(1) == "+1 more fields"


def test_js_luna_helpers_contains_field_cap_constant():
    """luna_helpers.js must define the FIELD_CAP value as a var."""
    from pathlib import Path
    js = (Path(__file__).parent.parent.parent / "js" / "luna_helpers.js").read_text()
    assert "FIELD_CAP" in js


def test_js_luna_helpers_contains_value_cap_constant():
    """luna_helpers.js must define the VALUE_CAP value as a var."""
    from pathlib import Path
    js = (Path(__file__).parent.parent.parent / "js" / "luna_helpers.js").read_text()
    assert "VALUE_CAP" in js


def test_js_luna_helpers_more_marker_present():
    """luna_helpers.js must emit '+K more fields' when truncating."""
    from pathlib import Path
    js = (Path(__file__).parent.parent.parent / "js" / "luna_helpers.js").read_text()
    assert "more fields" in js


# ── C3(b): self-compressing get_hierarchy ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_hierarchy_small_response_passthrough():
    """Small hierarchy (< size threshold) returned unchanged."""
    from luna_mcp.tools.scene_tools import register_scene_tools

    small = "Root [Transform]\n  Child [MeshRenderer]"
    calls = []

    async def fake_call(method, *args):
        calls.append(method)
        return small

    class FakeMCP:
        def tool(self, *a, **kw):
            def dec(f): return f
            return dec

    tools = register_scene_tools(FakeMCP(), fake_call, exposed=frozenset())
    result = await tools["get_hierarchy"][0]()
    assert result == small


@pytest.mark.asyncio
async def test_get_hierarchy_large_response_gets_distilled():
    """get_hierarchy auto-distills when response exceeds HIERARCHY_SIZE_THRESHOLD chars."""
    from luna_mcp.tools.scene_tools import register_scene_tools

    # Build a hierarchy large enough to trigger compression
    big_hierarchy = "\n".join(f"Object{i} [MeshRenderer, Collider]" for i in range(200))

    async def fake_call(method, *args):
        return big_hierarchy

    class FakeMCP:
        def tool(self, *a, **kw):
            def dec(f): return f
            return dec

    tools = register_scene_tools(FakeMCP(), fake_call, exposed=frozenset())
    result = await tools["get_hierarchy"][0]()
    # Must be shorter than original AND contain the distilled marker
    assert len(result) < len(big_hierarchy)
    assert "[DISTILLED]" in result


@pytest.mark.asyncio
async def test_get_hierarchy_distilled_marker_contains_stats():
    """Distilled output must contain object count stats."""
    from luna_mcp.tools.scene_tools import register_scene_tools

    big_hierarchy = "\n".join(f"Object{i} [MeshRenderer]" for i in range(200))

    async def fake_call(method, *args):
        return big_hierarchy

    class FakeMCP:
        def tool(self, *a, **kw):
            def dec(f): return f
            return dec

    tools = register_scene_tools(FakeMCP(), fake_call, exposed=frozenset())
    result = await tools["get_hierarchy"][0]()
    assert "200" in result  # total object count


@pytest.mark.asyncio
async def test_get_hierarchy_error_passthrough():
    """Error responses from JS are never distilled."""
    from luna_mcp.tools.scene_tools import register_scene_tools

    async def fake_call(method, *args):
        return "error: no scene"

    class FakeMCP:
        def tool(self, *a, **kw):
            def dec(f): return f
            return dec

    tools = register_scene_tools(FakeMCP(), fake_call, exposed=frozenset())
    result = await tools["get_hierarchy"][0]()
    assert result == "error: no scene"
    assert "[DISTILLED]" not in result


def test_hierarchy_size_threshold_constant_exists():
    """HIERARCHY_SIZE_THRESHOLD must be defined in scene_tools."""
    from luna_mcp.tools import scene_tools
    assert hasattr(scene_tools, "HIERARCHY_SIZE_THRESHOLD")
    assert isinstance(scene_tools.HIERARCHY_SIZE_THRESHOLD, int)
    assert scene_tools.HIERARCHY_SIZE_THRESHOLD > 0
