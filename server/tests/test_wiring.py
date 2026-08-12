"""Tests for wiring.py validation logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from luna_mcp.wiring import merge_tool_groups


def test_merge_raises_on_duplicate():
    all_tools = {"a": 1}
    with pytest.raises(ValueError, match="a"):
        merge_tool_groups(all_tools, {"a": 2})


def test_merge_succeeds_distinct():
    all_tools = {"a": 1}
    result = merge_tool_groups(all_tools, {"b": 2})
    assert result == {"b": 2}
    assert all_tools == {"a": 1, "b": 2}


def _make_mcp():
    mcp = MagicMock()
    mcp.tool = MagicMock(return_value=lambda fn: fn)
    return mcp


def test_exposed_tools_orphan_raises():
    """EXPOSED_TOOLS with a name not in registered tools should raise ValueError."""
    import luna_mcp.wiring as wiring

    original = wiring.EXPOSED_TOOLS.copy()
    wiring.EXPOSED_TOOLS.add("__nonexistent_tool_xyz__")
    try:
        with pytest.raises(ValueError, match="EXPOSED_TOOLS references unknown tools"):
            wiring.register_all_tools(
                mcp=_make_mcp(),
                call_fn=AsyncMock(),
                send_fn=AsyncMock(),
                get_bridge=lambda: None,
                ensure_connected=AsyncMock(),
                require_debugger=AsyncMock(),
                require_source_mapper=MagicMock(),
                get_typemap=lambda: None,
                budget_tracker=MagicMock(),
                budget_router=MagicMock(),
                get_brain_scanner=lambda: None,
            )
    finally:
        wiring.EXPOSED_TOOLS.discard("__nonexistent_tool_xyz__")
        # Restore original in case test modified it
        wiring.EXPOSED_TOOLS.clear()
        wiring.EXPOSED_TOOLS.update(original)


def test_exposed_tools_no_orphans_succeeds():
    """register_all_tools should succeed when EXPOSED_TOOLS has no orphans."""
    import luna_mcp.wiring as wiring

    result = wiring.register_all_tools(
        mcp=_make_mcp(),
        call_fn=AsyncMock(),
        send_fn=AsyncMock(),
        get_bridge=lambda: None,
        ensure_connected=AsyncMock(),
        require_debugger=AsyncMock(),
        require_source_mapper=MagicMock(),
        get_typemap=lambda: None,
        budget_tracker=MagicMock(),
        budget_router=MagicMock(),
        get_brain_scanner=lambda: None,
    )
    # Should return tuple of (all_tools, sampling, build_semantic, pc_validator)
    all_tools, sampling, build_semantic, pc_validator = result
    assert isinstance(all_tools, dict)
    assert len(all_tools) > 0
