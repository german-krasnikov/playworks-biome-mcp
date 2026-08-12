"""S5.3 — Luna issue seeds tests (RED phase)."""
import pytest

from luna_mcp.lessons.store import LessonStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test_lessons.db"
    s = LessonStore(db)
    yield s
    s.close()


def test_seed_luna_issues_returns_count(store):
    from luna_mcp.lessons.luna_issue_seeds import seed_luna_issues
    count = seed_luna_issues(store)
    assert count >= 6


def test_seed_luna_issues_idempotent(store):
    from luna_mcp.lessons.luna_issue_seeds import seed_luna_issues
    count1 = seed_luna_issues(store)
    count2 = seed_luna_issues(store)
    assert count1 == count2
    lessons = store.find_by_kind("*", "luna_build_issue")
    assert len(lessons) == count1


def test_find_by_kind_returns_at_least_6(store):
    from luna_mcp.lessons.luna_issue_seeds import seed_luna_issues
    seed_luna_issues(store)
    lessons = store.find_by_kind("*", "luna_build_issue")
    assert len(lessons) >= 6


def test_seeds_have_valid_fields(store):
    from luna_mcp.lessons.luna_issue_seeds import seed_luna_issues
    seed_luna_issues(store)
    lessons = store.find_by_kind("*", "luna_build_issue")
    for lesson in lessons:
        assert lesson.situation
        assert lesson.action
        assert lesson.pattern_kind == "luna_build_issue"


def test_typeloadexception_classifies_critical():
    """TypeLoadException in a console line → severity critical."""
    from luna_mcp.error_triage.triage import triage
    result = triage("TypeLoadException: Could not load type 'SomeClass'")
    assert result["groups"][0]["severity"] == "critical"


def test_missing_shader_variant_classifies_critical():
    """Missing shader variant → severity critical."""
    from luna_mcp.error_triage.triage import triage
    result = triage("Missing shader variant SVC_Luna_Standard")
    assert result["groups"][0]["severity"] == "critical"


def test_svc_luna_classifies_critical():
    """SVC_Luna → severity critical."""
    from luna_mcp.error_triage.triage import triage
    result = triage("Error: SVC_Luna shader compile failed")
    assert result["groups"][0]["severity"] == "critical"
