"""TDD tests for SessionHistory (feature #8: Budget Auto-tuning)."""
import threading
import time

# ── get_project_key ───────────────────────────────────────────────────────────

def test_get_project_key_uses_env_first(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_PROJECT", "my-game")
    from luna_mcp.budget.history import get_project_key
    key = get_project_key()
    assert len(key) == 12
    assert key.isalnum()


def test_get_project_key_falls_back_to_cwd(monkeypatch):
    monkeypatch.delenv("LUNA_PROJECT", raising=False)
    from luna_mcp.budget.history import get_project_key
    key = get_project_key()
    assert len(key) == 12
    assert key.isalnum()


def test_get_project_key_stable_same_env(monkeypatch):
    monkeypatch.setenv("LUNA_PROJECT", "stable-key")
    from luna_mcp.budget.history import get_project_key
    assert get_project_key() == get_project_key()


def test_get_project_key_different_for_different_env(monkeypatch):
    monkeypatch.setenv("LUNA_PROJECT", "proj-a")
    from luna_mcp.budget.history import get_project_key
    key_a = get_project_key()
    monkeypatch.setenv("LUNA_PROJECT", "proj-b")
    key_b = get_project_key()
    assert key_a != key_b


# ── SessionHistory CRUD ───────────────────────────────────────────────────────

def make_row(project_key="abc123", spent=1000, cap=30000, skipped=0, downgraded=0, hit_cap=0, success=1):
    from luna_mcp.budget.history import SessionRow
    return SessionRow(
        ts=time.time(),
        project_key=project_key,
        total_spent=spent,
        cap=cap,
        skipped=skipped,
        downgraded=downgraded,
        hit_cap=hit_cap,
        success=success,
    )


def test_record_persists_session(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    row = make_row(spent=5000)
    h.record(row)
    rows = h.recent("abc123")
    assert len(rows) == 1
    assert rows[0].total_spent == 5000
    h.close()


def test_recent_returns_ordered_desc(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    for i in range(3):
        row = make_row(spent=i * 1000)
        row = row.__class__(ts=float(i), **{k: getattr(row, k) for k in row.__dataclass_fields__ if k != "ts"})
        h.record(row)
    rows = h.recent("abc123")
    # Should be ordered DESC by ts
    assert rows[0].ts >= rows[1].ts >= rows[2].ts
    h.close()


def test_recent_limited(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    for i in range(10):
        h.record(make_row(spent=i * 100))
    rows = h.recent("abc123", limit=3)
    assert len(rows) == 3
    h.close()


def test_recent_filters_by_project_key(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    h.record(make_row(project_key="proj_a", spent=1000))
    h.record(make_row(project_key="proj_b", spent=2000))
    h.record(make_row(project_key="proj_a", spent=3000))
    rows_a = h.recent("proj_a")
    rows_b = h.recent("proj_b")
    assert len(rows_a) == 2
    assert len(rows_b) == 1
    assert all(r.project_key == "proj_a" for r in rows_a)
    h.close()


def test_recent_empty_returns_empty_list(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    rows = h.recent("no_such_key")
    assert rows == []
    h.close()


def test_concurrent_writes(tmp_path):
    from luna_mcp.budget.history import SessionHistory
    h = SessionHistory(tmp_path / "history.db")
    errors = []

    def write_row(i):
        try:
            h.record(make_row(spent=i * 100))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write_row, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    rows = h.recent("abc123")
    assert len(rows) == 5
    h.close()


def test_db_created_in_parent_dir(tmp_path):
    """SessionHistory creates parent dirs if missing."""
    from luna_mcp.budget.history import SessionHistory
    nested = tmp_path / "a" / "b" / "c" / "history.db"
    h = SessionHistory(nested)
    h.record(make_row())
    assert nested.exists()
    h.close()
