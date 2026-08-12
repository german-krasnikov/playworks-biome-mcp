"""Tests for Playworks-specific typemap seed lessons."""
import sqlite3

from luna_mcp.lessons.keys import class_hash
from luna_mcp.lessons.store import LessonStore
from luna_mcp.lessons.typemap_seeds import PLAYWORKS_SEEDS, seed_typemap_lessons


def _store(tmp_path) -> LessonStore:
    return LessonStore(tmp_path / "l.db")


def test_seed_typemap_inserts_5_playworks_lessons(tmp_path):
    store = _store(tmp_path)
    count = seed_typemap_lessons(store)
    assert count == 5
    store.close()


def test_button_seed_action_mentions_persistent_calls(tmp_path):
    store = _store(tmp_path)
    seed_typemap_lessons(store)
    ch = class_hash("UnityEngine.UI.Button")
    lessons = store.find_typemap("set_property", ch)
    assert len(lessons) >= 1
    action_lower = lessons[0].action.lower()
    assert "persistent" in action_lower or "persistentcall" in action_lower.replace(" ", "")
    store.close()


def test_image_seed_mentions_setmaterialdirty(tmp_path):
    store = _store(tmp_path)
    seed_typemap_lessons(store)
    ch = class_hash("UnityEngine.UI.Image")
    lessons = store.find_typemap("set_property", ch)
    assert len(lessons) >= 1
    assert "SetMaterialDirty" in lessons[0].action or "setmaterialdirty" in lessons[0].action.lower()
    store.close()


def test_seed_idempotent_run_twice(tmp_path):
    store = _store(tmp_path)
    c1 = seed_typemap_lessons(store)
    c2 = seed_typemap_lessons(store)
    assert c1 == c2 == 5
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    count = conn.execute("SELECT COUNT(*) FROM lessons WHERE source='seed'").fetchone()[0]
    conn.close()
    store.close()
    assert count == 5


def test_all_seeds_have_star_build_hash():
    for entry in PLAYWORKS_SEEDS:
        assert entry["lesson"].build_hash == "*"


def test_seeds_cover_key_unity_types():
    class_names = [e["class_name"] for e in PLAYWORKS_SEEDS]
    assert "UnityEngine.UI.Button" in class_names
    assert "UnityEngine.UI.Image" in class_names
    assert "UnityEngine.ParticleSystem" in class_names
