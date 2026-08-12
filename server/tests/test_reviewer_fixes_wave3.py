"""RED tests for Wave 3 code-reviewer fixes (C1-B, M1, M2, M4, m1, m2, m3)."""
import pathlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── C1-B: find_lesson_for_class wired into _hinted-like wrapper ──────────────

@pytest.mark.asyncio
async def test_lesson_injected_for_set_property_with_known_class(tmp_path):
    """LESSON: prefix injected when store has lesson for the class."""
    from luna_mcp.lessons.keys import class_hash, sig_hash
    from luna_mcp.lessons.store import Lesson, LessonStore

    store = LessonStore(tmp_path / "l.db")
    ch = class_hash("UnityEngine.UI.Button")
    sh = sig_hash({"methods": ["onClick"]})
    lesson = Lesson("*", "set_property", "k", "onClick access", "use .onClick.AddListener()")
    store.add_typemap(lesson, ch, sh, "7.1.0")

    from luna_mcp.server_helpers import _maybe_inject_lesson
    kw = {"component_type": "UnityEngine.UI.Button", "prop": "onClick", "path": "Root/Btn"}
    lesson = _maybe_inject_lesson("set_property", kw, store)
    assert lesson is not None and "LESSON:" in lesson
    store.close()


@pytest.mark.asyncio
async def test_no_lesson_injected_for_unknown_class(tmp_path):
    """No LESSON: prefix when class has no typemap lessons."""
    from luna_mcp.lessons.store import LessonStore

    store = LessonStore(tmp_path / "l.db")

    from luna_mcp.server_helpers import _maybe_inject_lesson
    kw = {"component_type": "UnknownClass", "prop": "foo", "path": "Root/X"}
    lesson = _maybe_inject_lesson("set_property", kw, store)
    assert lesson is None
    store.close()


# ── M1: hint lengths ≤ 80 chars ──────────────────────────────────────────────

@pytest.mark.parametrize("rule_id,setup_calls", [
    ("console-poll", [
        ("get_console", {}), ("get_console", {}), ("get_console", {}),
    ]),
    ("detail-redundant", [
        ("get_object_detail", {"path": "Root/Btn"}),
    ]),
    ("pause-leak", [
        ("pause_game", {}),
        *([("get_hierarchy", {})] * 8),
    ]),
    ("diag-thrash", [
        ("set_property", {"path": "X"}, "[REFLECT:mismatch: err]"),
        ("diagnose_object", {"path": "Root/A"}),
    ]),
])
def test_hint_length_80_char_limit(rule_id, setup_calls):
    from luna_mcp.hinter import ToolHinter

    h = ToolHinter()
    last_result = None

    if rule_id == "console-poll":
        for c in setup_calls:
            last_result = h.observe(c[0], c[1] if len(c) > 1 else {}, "ok")
        last_result = h.observe("get_console", {}, "ok")

    elif rule_id == "detail-redundant":
        h.observe("get_object_detail", {"path": "Root/Btn"}, "ok")
        last_result = h.observe("get_component", {"path": "Root/Btn", "component_type": "Image"}, "ok")

    elif rule_id == "pause-leak":
        h.observe("pause_game", {}, "ok")
        for _ in range(8):
            h.observe("get_hierarchy", {}, "ok")
        last_result = h.observe("get_hierarchy", {}, "ok")

    elif rule_id == "diag-thrash":
        h.observe("set_property", {"path": "X"}, "[REFLECT:mismatch: err]")
        h.observe("diagnose_object", {"path": "Root/A"}, "ok")
        last_result = h.observe("diagnose_object", {"path": "Root/B"}, "ok")

    assert last_result is not None, f"Rule {rule_id} did not fire"
    assert len(last_result) <= 80, f"Rule {rule_id} hint exceeds 80 chars: {len(last_result)} '{last_result}'"


# ── M2: fps=0 raises ValueError ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capture_fps_zero_raises(tmp_path):
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=AsyncMock(), tmp_dir=tmp_path)
    with pytest.raises(ValueError, match="fps must be"):
        await cap.capture(duration_ms=1000, fps=0)


@pytest.mark.asyncio
async def test_capture_fps_negative_raises(tmp_path):
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=AsyncMock(), tmp_dir=tmp_path)
    with pytest.raises(ValueError, match="fps must be"):
        await cap.capture(duration_ms=1000, fps=-1)


# ── M4: LUNA_HINTER=0 disables only hints, not degradation ───────────────────

def test_degradation_fires_when_chrome_down():
    """GracefulDegradation returns DEGRADED when bridge.connected=False."""
    from luna_mcp.degradation import GracefulDegradation

    bridge = MagicMock()
    bridge.connected = False
    d = GracefulDegradation(lambda: bridge, None, lambda: None)

    result = d.check("get_hierarchy", {})
    assert "DEGRADED:chrome" in result


def test_hinter_budget_deaf_fires():
    """ToolHinter detects budget-deaf pattern (skipped result repeated)."""
    from luna_mcp.hinter import ToolHinter
    h = ToolHinter()

    h.observe("get_hierarchy", {}, "[skipped get_hierarchy: budget exhausted]")
    result = h.observe("get_hierarchy", {}, "[skipped get_hierarchy: budget exhausted]")

    assert result is not None and "budget-deaf" in result


# ── m1: lost-context rule uses subsequence in last 5 ─────────────────────────

def test_lost_context_fires_with_interleaved_calls():
    """find_objects → other_tool → get_hierarchy → find_objects triggers hint."""
    from luna_mcp.hinter import ToolHinter
    h = ToolHinter()
    h.observe("find_objects", {"query": "Btn"}, "ok")
    h.observe("get_component", {"path": "Root/Btn"}, "ok")
    h.observe("get_hierarchy", {}, "ok")
    result = h.observe("find_objects", {"query": "Btn"}, "ok")
    assert result is not None
    assert "lost-context" in result


def test_lost_context_no_fire_without_get_hierarchy():
    """find_objects × 2 without get_hierarchy between them → no hint."""
    from luna_mcp.hinter import ToolHinter
    h = ToolHinter()
    h.observe("find_objects", {"query": "Btn"}, "ok")
    h.observe("get_component", {"path": "Root/Btn"}, "ok")
    result = h.observe("find_objects", {"query": "Btn"}, "ok")
    # should NOT fire since no get_hierarchy between
    assert result is None or "lost-context" not in result


# ── m2: _LabelCache true LRU (access updates timestamp) ──────────────────────

def test_label_cache_lru_access_updates_timestamp():
    """Accessing an item prevents it from being the eviction victim."""
    from luna_mcp.timeline import TimelineFrame, _LabelCache
    frames = [TimelineFrame(t_ms=0, path=pathlib.Path("/tmp/x.png"))]

    cache = _LabelCache(max_labels=2, ttl_s=60.0)
    cache.set("a", frames)
    time.sleep(0.01)
    cache.set("b", frames)

    # access "a" to refresh its timestamp
    cache.get("a")
    time.sleep(0.01)

    # insert "c" — with true LRU, "b" (least recently used) should be evicted, not "a"
    cache.set("c", frames)

    assert cache.get("a") is not None, "a should survive (was recently accessed)"
    assert cache.get("c") is not None, "c should be present (just inserted)"
    # b was evicted
    assert cache.get("b") is None, "b should be evicted (least recently used)"
