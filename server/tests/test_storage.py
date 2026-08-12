"""Tests for build_diff/storage.py — RED phase."""

from luna_mcp.build_diff.indexer import BuildIndex
from luna_mcp.build_diff.storage import BuildStore


def _make_store(tmp_path):
    return BuildStore(tmp_path / "store")


def _make_manifest(tmp_path, label, files):
    root = tmp_path / label
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (root / name).write_text(content)
    return BuildIndex.scan(root, label)


def test_storage_save_load_roundtrip(tmp_path):
    s = _make_store(tmp_path)
    m = _make_manifest(tmp_path, "v1", {"main.js": "hello"})
    s.save(m)
    loaded = s.load("v1")
    assert loaded is not None
    assert loaded.label == "v1"
    assert len(loaded.files) == 1
    assert loaded.files[0].path == "main.js"


def test_storage_load_missing_returns_none(tmp_path):
    s = _make_store(tmp_path)
    assert s.load("nonexistent") is None


def test_storage_load_corrupt_returns_none(tmp_path):
    s = _make_store(tmp_path)
    s._dir.mkdir(parents=True, exist_ok=True)
    (s._dir / "x.json").write_text("not valid json {")
    assert s.load("x") is None


def test_storage_list_skips_corrupt(tmp_path):
    s = _make_store(tmp_path)
    m = _make_manifest(tmp_path, "good", {"f.js": "x"})
    s.save(m)
    # inject corrupt file
    (s._dir / "bad.json").write_text("{{broken")
    result = s.list_all()
    labels = [r.label for r in result]
    assert "good" in labels
    assert "bad" not in labels


def test_storage_list_empty_when_no_dir(tmp_path):
    s = _make_store(tmp_path)
    assert s.list_all() == []
