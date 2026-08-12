"""Tests for tappable_tools (S2.2)."""
import pathlib

import pytest

_JS_FILE = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"

_RECTS_FIXTURE = "Panel/Button|0|0|800|600|Button\nPanel/CTA|300|400|120|40|Button"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


def test_tappable_returns_2_entries():
    from luna_mcp.tools.tappable_tools import register_tappable_tools
    tools = register_tappable_tools(FakeMCP(), None)
    assert len(tools) == 2
    assert "why_not_tappable" in tools
    assert "hit_test" in tools


@pytest.mark.asyncio
async def test_why_not_tappable_interactable():
    from luna_mcp.tools.tappable_tools import register_tappable_tools

    async def call_fn(method, *args):
        return "IsInteractable: True\nenabled: True\nactiveSelf: True\nraycastTarget: True"

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["why_not_tappable"]
    result = await fn(path="UI/Button")
    assert "IsInteractable" in result


@pytest.mark.asyncio
async def test_why_not_tappable_blocked_by_canvasgroup():
    from luna_mcp.tools.tappable_tools import register_tappable_tools

    async def call_fn(method, *args):
        return "IsInteractable: False\nBlockedBy: CanvasGroup at Panel"

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["why_not_tappable"]
    result = await fn(path="UI/Button")
    assert "CanvasGroup" in result or "Blocked" in result or "False" in result


@pytest.mark.asyncio
async def test_hit_test_parses_and_filters():
    """hit_test(310, 410) on fixture should return CTA (deepest) first."""
    from luna_mcp.tools.tappable_tools import register_tappable_tools

    async def call_fn(method, *args):
        return _RECTS_FIXTURE

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["hit_test"]
    result = await fn(x=310.0, y=410.0)
    assert "CTA" in result
    # CTA is deeper (Panel/CTA has more path segments) — should be first
    lines = [l for l in result.strip().split("\n") if l]
    assert lines[0].startswith("Panel/CTA")


@pytest.mark.asyncio
async def test_hit_test_no_match():
    from luna_mcp.tools.tappable_tools import register_tappable_tools

    async def call_fn(method, *args):
        return _RECTS_FIXTURE

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["hit_test"]
    result = await fn(x=0.0, y=700.0)
    assert "no interactable" in result


@pytest.mark.asyncio
async def test_hit_test_topmost_is_deepest_path():
    """Deeper path depth = more '/' chars => sorted DESC means deepest first."""
    from luna_mcp.tools.tappable_tools import register_tappable_tools
    rects = "A/B/C|100|100|200|200|Button\nA/B|50|50|400|400|Button"

    async def call_fn(method, *args):
        return rects

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["hit_test"]
    result = await fn(x=150.0, y=150.0)
    lines = [l for l in result.strip().split("\n") if l]
    # A/B/C has depth 2; A/B has depth 1 — A/B/C should come first
    assert lines[0].startswith("A/B/C")


@pytest.mark.asyncio
async def test_hit_test_handles_malformed_line():
    from luna_mcp.tools.tappable_tools import register_tappable_tools
    rects = "bad_line_no_pipes\nPanel/CTA|300|400|120|40|Button"

    async def call_fn(method, *args):
        return rects

    tools = register_tappable_tools(FakeMCP(), call_fn)
    fn, _ = tools["hit_test"]
    result = await fn(x=310.0, y=410.0)
    # malformed line ignored, CTA should match
    assert "CTA" in result


def test_js_whyNotTappable_present():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "whyNotTappable:" in text
