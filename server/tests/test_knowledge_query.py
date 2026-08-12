"""Tests for PhysicsKnowledge query."""

import pytest

from luna_mcp.lessons.store import LessonStore
from luna_mcp.physics_detective.knowledge_query import PhysicsKnowledge
from luna_mcp.physics_detective.seeds import seed_physics_lessons


@pytest.fixture
def store(tmp_path):
    s = LessonStore(tmp_path / "lessons.db")
    seed_physics_lessons(s)
    yield s
    s.close()


def test_query_goblin_jitter(store):
    kb = PhysicsKnowledge(store)
    results = kb.query("goblin", "object is jiggling and shaking")
    assert len(results) > 0
    assert all(r.pattern_kind == "physics_goblin" for r in results)


def test_query_verlet_explosion(store):
    kb = PhysicsKnowledge(store)
    results = kb.query("verlet", "rope explode from stiffness")
    assert len(results) > 0
    assert all(r.pattern_kind == "physics_verlet" for r in results)


def test_query_baked_desync(store):
    kb = PhysicsKnowledge(store)
    results = kb.query("baked", "playback speed desync animation")
    assert len(results) > 0
    assert all(r.pattern_kind == "physics_baked" for r in results)


def test_query_filters_by_backend(store):
    kb = PhysicsKnowledge(store)
    # asking goblin with a verlet symptom — should find no goblin lessons for it
    results_goblin = kb.query("goblin", "stiffness rope explode")
    results_verlet = kb.query("verlet", "stiffness rope explode")
    # verlet has explosion lesson; goblin has none for stiffness rope
    assert all(r.pattern_kind == "physics_goblin" for r in results_goblin)
    assert all(r.pattern_kind == "physics_verlet" for r in results_verlet)
    assert len(results_verlet) >= 1


def test_query_returns_max_3(store):
    kb = PhysicsKnowledge(store)
    # broad query that might match many
    results = kb.query("goblin", "kinematic velocity compound goblin")
    assert len(results) <= 3


def test_query_no_store():
    kb = PhysicsKnowledge(None)
    results = kb.query("goblin", "something wrong")
    assert results == []


def test_query_unified(store):
    kb = PhysicsKnowledge(store)
    results = kb.query("unified", "hero not pushing push radius")
    assert len(results) > 0
    assert results[0].pattern_kind == "physics_unified"


def test_query_unmatched_symptom(store):
    kb = PhysicsKnowledge(store)
    results = kb.query("goblin", "absolutely random unrelated text xyz")
    assert results == []
