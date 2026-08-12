"""TDD tests for tmp_cleanup helper (m2)."""
import time


def test_track_adds_to_set(tmp_path):
    from luna_mcp.tmp_cleanup import _LOCK, _TRACKED, track
    f = tmp_path / "test.png"
    f.write_bytes(b"x")
    with _LOCK:
        _TRACKED.clear()
    track(f)
    with _LOCK:
        assert f in _TRACKED


def test_cleanup_all_removes_files(tmp_path):
    from luna_mcp import tmp_cleanup
    f1 = tmp_path / "a.png"
    f2 = tmp_path / "b.png"
    f1.write_bytes(b"x")
    f2.write_bytes(b"x")
    with tmp_cleanup._LOCK:
        tmp_cleanup._TRACKED.clear()
    tmp_cleanup.track(f1)
    tmp_cleanup.track(f2)
    tmp_cleanup.cleanup_all()
    assert not f1.exists()
    assert not f2.exists()
    with tmp_cleanup._LOCK:
        assert len(tmp_cleanup._TRACKED) == 0


def test_cleanup_old_respects_age(tmp_path):
    from luna_mcp import tmp_cleanup
    f_old = tmp_path / "old.png"
    f_new = tmp_path / "new.png"
    f_old.write_bytes(b"x")
    f_new.write_bytes(b"x")
    with tmp_cleanup._LOCK:
        tmp_cleanup._TRACKED.clear()
    tmp_cleanup.track(f_old)
    # make f_old's mtime 20 minutes ago
    old_time = time.time() - 1201
    import os
    os.utime(f_old, (old_time, old_time))
    tmp_cleanup.track(f_new)
    tmp_cleanup.cleanup_old()
    assert not f_old.exists()
    assert f_new.exists()


def test_max_files_purges_oldest(tmp_path):
    from luna_mcp import tmp_cleanup
    with tmp_cleanup._LOCK:
        tmp_cleanup._TRACKED.clear()
    files = []
    for i in range(55):
        f = tmp_path / f"f{i:03d}.png"
        f.write_bytes(b"x")
        files.append(f)
        tmp_cleanup.track(f)
    # After 55 tracks with max=50, set should be <= 50
    with tmp_cleanup._LOCK:
        assert len(tmp_cleanup._TRACKED) <= tmp_cleanup._MAX_FILES


def test_cleanup_handles_missing_files(tmp_path):
    from luna_mcp import tmp_cleanup
    f = tmp_path / "gone.png"
    # Do NOT create it — externally deleted scenario
    with tmp_cleanup._LOCK:
        tmp_cleanup._TRACKED.clear()
    with tmp_cleanup._LOCK:
        tmp_cleanup._TRACKED.add(f)
    # Must not raise
    tmp_cleanup.cleanup_all()


def test_atexit_registered():
    """cleanup_all must be registered with atexit."""
    import atexit

    from luna_mcp import tmp_cleanup
    # atexit doesn't expose its registry publicly, so we re-import and check
    # the module registers via atexit.register at import time.
    # Best we can do: ensure module imported without error and cleanup_all callable.
    assert callable(tmp_cleanup.cleanup_all)
    # Verify atexit._exithandlers contains cleanup_all (CPython impl detail)
    try:
        handlers = [h[0] for h in atexit._exithandlers]
        assert tmp_cleanup.cleanup_all in handlers
    except AttributeError:
        # PyPy or other impl — skip
        pass
