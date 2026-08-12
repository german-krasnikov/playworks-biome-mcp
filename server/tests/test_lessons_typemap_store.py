"""Tests for typemap-aware LessonStore extensions."""
import sqlite3

from luna_mcp.lessons.keys import class_hash, sig_hash
from luna_mcp.lessons.store import Lesson, LessonStore


def _store(tmp_path) -> LessonStore:
    return LessonStore(tmp_path / "l.db")


def test_migrate_schema_adds_columns_idempotently(tmp_path):
    store = _store(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(lessons)").fetchall()}
    conn.close()
    store.close()
    assert "class_hash" in cols
    assert "sig_hash" in cols
    assert "typemap_version" in cols
    assert "deprecated" in cols
    assert "source" in cols

    # idempotent — re-create store doesn't crash
    store2 = _store(tmp_path)
    store2.close()


def test_add_typemap_persists_class_hash(tmp_path):
    store = _store(tmp_path)
    L = Lesson("*", "set_property", "k", "situation text", "do X")
    ch = class_hash("UnityEngine.UI.Button")
    sh = sig_hash({"methods": ["OnClick"], "fields": []})
    store.add_typemap(L, ch, sh, "7.1.0")
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    row = conn.execute("SELECT class_hash, sig_hash, typemap_version, deprecated FROM lessons WHERE class_hash=?", (ch,)).fetchone()
    conn.close()
    store.close()
    assert row is not None
    assert row[0] == ch
    assert row[1] == sh
    assert row[2] == "7.1.0"
    assert row[3] == 0


def test_find_typemap_returns_lesson_for_class(tmp_path):
    store = _store(tmp_path)
    L = Lesson("*", "set_property", "k", "onClick field", "use Bridge.Reflection")
    ch = class_hash("UnityEngine.UI.Button")
    sh = sig_hash({"methods": ["OnClick"], "fields": ["onClick"]})
    store.add_typemap(L, ch, sh, "7.1.0")
    results = store.find_typemap("set_property", ch)
    assert len(results) == 1
    assert results[0].action == "use Bridge.Reflection"
    store.close()


def test_find_typemap_filters_deprecated(tmp_path):
    store = _store(tmp_path)
    L = Lesson("*", "set_property", "k", "old situation", "old action")
    ch = class_hash("UnityEngine.UI.Button")
    sh = sig_hash({"methods": [], "fields": ["old"]})
    store.add_typemap(L, ch, sh, "7.1.0")
    # deprecate it
    store.deprecate_by_signature_change(ch, "new_sig_different")
    results = store.find_typemap("set_property", ch)
    assert results == []
    store.close()


def test_find_typemap_situation_substring(tmp_path):
    store = _store(tmp_path)
    ch = class_hash("UnityEngine.UI.Image")
    sh = sig_hash({"methods": [], "fields": ["fillAmount"]})
    L = Lesson("*", "set_property", "k", "fillAmount mutation", "call SetMaterialDirty")
    store.add_typemap(L, ch, sh, "7.1.0")
    results = store.find_typemap("set_property", ch, "fillAmount")
    assert len(results) == 1
    results_none = store.find_typemap("set_property", ch, "notpresent")
    assert results_none == []
    store.close()


def test_find_typemap_returns_empty_no_match(tmp_path):
    store = _store(tmp_path)
    ch = class_hash("SomeUnknownClass")
    results = store.find_typemap("set_property", ch)
    assert results == []
    store.close()


def test_deprecate_by_signature_change_marks_old(tmp_path):
    store = _store(tmp_path)
    ch = class_hash("UnityEngine.ParticleSystem")
    old_sh = sig_hash({"methods": ["Play"], "fields": ["loop"]})
    new_sh = sig_hash({"methods": ["Play"], "fields": ["looping"]})
    L = Lesson("*", "set_property", "k", "loop setting", "use main module")
    store.add_typemap(L, ch, old_sh, "7.1.0")
    count = store.deprecate_by_signature_change(ch, new_sh)
    assert count == 1
    results = store.find_typemap("set_property", ch)
    assert results == []
    store.close()


def test_seed_typemap_idempotent(tmp_path):
    """Running seed twice doesn't duplicate rows; action updates for source=seed."""
    from luna_mcp.lessons.typemap_seeds import seed_typemap_lessons
    store = _store(tmp_path)
    c1 = seed_typemap_lessons(store)
    c2 = seed_typemap_lessons(store)
    assert c1 == c2 == 5
    # count rows
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    count = conn.execute("SELECT COUNT(*) FROM lessons WHERE source='seed'").fetchone()[0]
    conn.close()
    store.close()
    assert count == 5
