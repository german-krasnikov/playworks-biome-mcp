"""Tests for typemap-aware matcher helper."""
from luna_mcp.lessons.keys import class_hash, sig_hash
from luna_mcp.lessons.matcher import find_lesson_for_class
from luna_mcp.lessons.store import Lesson, LessonStore


def _store(tmp_path) -> LessonStore:
    return LessonStore(tmp_path / "l.db")


def _add(store, class_name: str, cmd: str, situation: str, action: str):
    ch = class_hash(class_name)
    sh = sig_hash({"methods": [], "fields": []})
    L = Lesson("*", cmd, "k", situation, action)
    store.add_typemap(L, ch, sh, "7.1.0")


def test_find_lesson_for_class_returns_action(tmp_path):
    store = _store(tmp_path)
    _add(store, "UnityEngine.UI.Button", "set_property", "onClick", "use Bridge.Reflection")
    result = find_lesson_for_class(store, "set_property", "UnityEngine.UI.Button")
    assert result is not None
    assert "Bridge.Reflection" in result
    store.close()


def test_find_lesson_for_class_no_match_returns_none(tmp_path):
    store = _store(tmp_path)
    result = find_lesson_for_class(store, "set_property", "UnknownClass.Whatever")
    assert result is None
    store.close()


def test_find_lesson_for_class_empty_name_returns_none(tmp_path):
    store = _store(tmp_path)
    result = find_lesson_for_class(store, "set_property", "")
    assert result is None
    store.close()


def test_find_lesson_for_class_truncates_long_action(tmp_path):
    store = _store(tmp_path)
    long_action = "A" * 200
    _add(store, "LongClass", "eval_js", "some situation", long_action)
    result = find_lesson_for_class(store, "eval_js", "LongClass")
    assert result is not None
    # hint must be <= "LESSON: " (8) + 120 chars = 128 chars
    assert len(result) <= 128
    store.close()


def test_find_lesson_for_class_with_situation_hint(tmp_path):
    store = _store(tmp_path)
    _add(store, "UnityEngine.UI.Image", "set_property", "fillAmount color change", "call SetMaterialDirty")
    # wrong hint — no match
    r_no = find_lesson_for_class(store, "set_property", "UnityEngine.UI.Image", "nomatch_xyz")
    assert r_no is None
    # correct hint
    r_yes = find_lesson_for_class(store, "set_property", "UnityEngine.UI.Image", "fillAmount")
    assert r_yes is not None
    store.close()
