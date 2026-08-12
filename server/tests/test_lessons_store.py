"""Tests for LessonStore and seeds."""

from luna_mcp.lessons.matcher import matches
from luna_mcp.lessons.seeds import LUNA_SEEDS, seed_default
from luna_mcp.lessons.store import Lesson, LessonStore, _project_namespace

# --- LessonStore ---

def test_create_db_schema(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    store.close()
    assert "lessons" in tables


def test_add_inserts(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    L = Lesson("abc", "set_property", "type", "situation text", "do this")
    store.add(L)
    results = store.find("set_property", "abc")
    assert len(results) == 1
    assert results[0].action == "do this"
    store.close()


def test_add_idempotent_via_upsert(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    L = Lesson("abc", "eval_js", "kind", "sit", "act")
    store.add(L)
    store.add(L)
    store.add(L)
    results = store.find("eval_js", "abc")
    assert len(results) == 1
    assert results[0].hits == 3
    store.close()


def test_find_exact_build_wins_over_star(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    generic = Lesson("*", "eval_js", "k", "situation", "generic action")
    specific = Lesson("deadbeef", "eval_js", "k", "situation", "specific action")
    store.add(generic)
    store.add(specific)
    results = store.find("eval_js", "deadbeef")
    # exact build_hash result should come first
    assert results[0].action == "specific action"
    store.close()


def test_find_situation_substr(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    L = Lesson("*", "set_property", "t", "castToUnityType error occurred", "fix it")
    store.add(L)
    results = store.find("set_property", "*", "castToUnity")
    assert len(results) == 1
    results2 = store.find("set_property", "*", "noMatchHere")
    assert len(results2) == 0
    store.close()


def test_find_returns_empty_no_match(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    results = store.find("unknown_cmd", "hash")
    assert results == []
    store.close()


def test_prune_keeps_high_hits(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    # Add 10 lessons, give some of them many hits
    for i in range(10):
        L = Lesson("*", f"cmd_{i}", "k", f"sit_{i}", f"act_{i}")
        store.add(L)
    # Manually bump hits for first 5
    for i in range(5):
        store.add(Lesson("*", f"cmd_{i}", "k", f"sit_{i}", f"act_{i}_updated"))
    # Prune to keep only 5
    pruned = store.prune(max_rows=5)
    assert pruned == 5
    store.close()


def test_prune_no_op_when_within_limit(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.add(Lesson("*", "cmd", "k", "s", "a"))
    pruned = store.prune(max_rows=100)
    assert pruned == 0
    store.close()


def test_seed_default_idempotent(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    count1 = seed_default(store)
    count2 = seed_default(store)
    assert count1 == count2 == len(LUNA_SEEDS)
    # No duplicate rows
    results = store.find("set_property", "*")
    assert len(results) >= 1
    store.close()


def test_seed_default_luna_seeds_have_star_build(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    seed_default(store)
    for seed in LUNA_SEEDS:
        assert seed.build_hash == "*"
    store.close()


# --- matcher ---

def test_matches_regex():
    assert matches("castToUnityType.*error", "castToUnityType some error")


def test_matches_no_match():
    assert not matches("castToUnityType", "unrelated error")


def test_matches_invalid_regex_falls_back_to_substr():
    assert matches("[invalid(", "[invalid(")


def test_project_namespace_default():
    ns = _project_namespace()
    assert isinstance(ns, str)
    assert len(ns) > 0


# ── m4: update_action flag for seed re-seeding ───────────────────────────────

def test_add_update_action_updates_action(tmp_path):
    """m4: add(lesson, update_action=True) must update action in DB on conflict."""
    store = LessonStore(tmp_path / "l.db")
    L1 = Lesson("*", "eval_js", "k", "sit", "old action")
    store.add(L1)
    L2 = Lesson("*", "eval_js", "k", "sit", "new action")
    store.add(L2, update_action=True)
    results = store.find("eval_js", "*")
    assert results[0].action == "new action"
    store.close()


def test_add_no_update_action_preserves_old_action(tmp_path):
    """m4: without update_action=True, action is NOT updated on conflict."""
    store = LessonStore(tmp_path / "l.db")
    L1 = Lesson("*", "eval_js", "k", "sit", "original")
    store.add(L1)
    L2 = Lesson("*", "eval_js", "k", "sit", "changed")
    store.add(L2)  # update_action=False by default
    results = store.find("eval_js", "*")
    assert results[0].action == "original"
    store.close()


def test_seed_default_updates_actions(tmp_path):
    """m4: re-seeding with updated LUNA_SEEDS should update actions in DB."""
    store = LessonStore(tmp_path / "l.db")
    # First seed
    seed_default(store)
    # Manually corrupt an action
    store._conn.execute(
        "UPDATE lessons SET action='corrupted' WHERE cmd='set_property' AND build_hash='*'"
    )
    store._conn.commit()
    # Re-seed — must restore correct action
    seed_default(store)
    results = store.find("set_property", "*")
    assert results[0].action != "corrupted"
    store.close()


# m4: find_by_kind direct tests
def test_find_by_kind_returns_only_matching(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.add(Lesson(build_hash="*", cmd="x", pattern_kind="kind_a", situation="s1", action="a1"))
    store.add(Lesson(build_hash="*", cmd="x", pattern_kind="kind_b", situation="s2", action="a2"))
    result = store.find_by_kind(cmd="x", pattern_kind="kind_a")
    assert len(result) == 1
    assert result[0].action == "a1"
    store.close()


def test_find_by_kind_empty_returns_empty(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    assert store.find_by_kind(cmd="missing", pattern_kind="missing") == []
    store.close()


# ── Public versions-table API ────────────────────────────────────────────────

def test_ensure_versions_table_creates_table(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "l.db"))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    store.close()
    assert "typemap_versions" in tables


def test_ensure_versions_table_idempotent(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    store.ensure_versions_table()  # must not raise
    store.close()


def test_get_version_returns_none_when_missing(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    assert store.get_version("nonexistent_hash") is None
    store.close()


def test_upsert_version_stores_and_retrieves(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    store.upsert_version("ch1", "sh1", "7.1.0")
    row = store.get_version("ch1")
    assert row is not None
    assert row["sig_hash"] == "sh1"
    assert row["typemap_version"] == "7.1.0"
    store.close()


def test_upsert_version_overwrites_on_conflict(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    store.upsert_version("ch1", "sh_old", "7.1.0")
    store.upsert_version("ch1", "sh_new", "7.2.0")
    row = store.get_version("ch1")
    assert row["sig_hash"] == "sh_new"
    assert row["typemap_version"] == "7.2.0"
    store.close()


def test_swap_version_if_changed_first_sighting_returns_sentinel(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    result = store.swap_version_if_changed("ch_new", "sh1", "7.1.0")
    assert result is LessonStore._FIRST_SEEN
    row = store.get_version("ch_new")
    assert row["sig_hash"] == "sh1"
    store.close()


def test_swap_version_if_changed_same_sig_returns_none(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    store.upsert_version("ch1", "sh1", "7.1.0")
    result = store.swap_version_if_changed("ch1", "sh1", "7.1.0")
    assert result is None  # same sig — no drift
    store.close()


def test_swap_version_if_changed_returns_old_sig_on_drift(tmp_path):
    store = LessonStore(tmp_path / "l.db")
    store.ensure_versions_table()
    store.upsert_version("ch1", "sh_old", "7.1.0")
    result = store.swap_version_if_changed("ch1", "sh_new", "7.2.0")
    assert result == "sh_old"  # returns old sig so caller can deprecate
    row = store.get_version("ch1")
    assert row["sig_hash"] == "sh_new"  # updated atomically
    store.close()
