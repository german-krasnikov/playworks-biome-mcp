"""Tests for physics lesson seeds."""
from luna_mcp.lessons.store import LessonStore
from luna_mcp.physics_detective.seeds import PHYSICS_SEEDS, seed_physics_lessons


def test_9_seeds_present(tmp_path):
    store = LessonStore(tmp_path / "lessons.db")
    n = seed_physics_lessons(store)
    assert n == 9
    store.close()


def test_idempotent_re_seed(tmp_path):
    store = LessonStore(tmp_path / "lessons.db")
    seed_physics_lessons(store)
    seed_physics_lessons(store)
    all_lessons = store.find(cmd="diagnose_physics", build_hash="*")
    assert len(all_lessons) <= 9  # no duplicates beyond limit=5, but hits increment
    store.close()


# M2: vacuous idempotency — proper per-kind count via find_by_kind
def test_seed_idempotent_two_runs(tmp_path):
    store = LessonStore(tmp_path / "lessons.db")
    seed_physics_lessons(store)
    seed_physics_lessons(store)
    counts = {}
    for kind in ["physics_goblin", "physics_verlet", "physics_baked", "physics_unified"]:
        counts[kind] = len(store.find_by_kind(cmd="diagnose_physics", pattern_kind=kind))
    total = sum(counts.values())
    assert total == 9, f"Expected 9 unique seeds, got {total}: {counts}"
    assert counts["physics_goblin"] == 3
    assert counts["physics_verlet"] == 3
    assert counts["physics_baked"] == 2
    assert counts["physics_unified"] == 1
    store.close()


def test_all_backends_covered(tmp_path):
    store = LessonStore(tmp_path / "lessons.db")
    seed_physics_lessons(store)
    # Fetch all by brute force iterating seeds
    found_kinds = {L.pattern_kind for L in PHYSICS_SEEDS}
    assert "physics_goblin" in found_kinds
    assert "physics_verlet" in found_kinds
    assert "physics_baked" in found_kinds
    assert "physics_unified" in found_kinds
    store.close()


def test_goblin_seeds_count():
    goblin = [L for L in PHYSICS_SEEDS if L.pattern_kind == "physics_goblin"]
    assert len(goblin) == 3


def test_verlet_seeds_count():
    verlet = [L for L in PHYSICS_SEEDS if L.pattern_kind == "physics_verlet"]
    assert len(verlet) == 3


def test_baked_seeds_count():
    baked = [L for L in PHYSICS_SEEDS if L.pattern_kind == "physics_baked"]
    assert len(baked) == 2


def test_unified_seeds_count():
    unified = [L for L in PHYSICS_SEEDS if L.pattern_kind == "physics_unified"]
    assert len(unified) == 1


def test_seeds_have_required_fields():
    for L in PHYSICS_SEEDS:
        assert L.build_hash == "*"
        assert L.cmd == "diagnose_physics"
        assert L.situation
        assert L.action
        assert L.token_cost > 0


def test_seeds_actions_not_empty():
    for L in PHYSICS_SEEDS:
        assert len(L.action) > 20, f"Action too short for {L.pattern_kind}: {L.action}"
