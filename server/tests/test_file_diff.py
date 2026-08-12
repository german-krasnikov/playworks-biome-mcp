"""Tests for build_diff/file_diff.py — RED phase."""
import pathlib

from luna_mcp.build_diff.file_diff import diff_manifests, format_text
from luna_mcp.build_diff.indexer import BuildIndex, Manifest


def _make_manifest(root, label, files: dict[str, str]) -> Manifest:
    """files = {rel_path: content}"""
    p = pathlib.Path(root)
    p.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        fpath = p / name
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content)
    return BuildIndex.scan(p, label)


def test_diff_empty_manifests_no_changes(tmp_path):
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir(); b_dir.mkdir()
    a = BuildIndex.scan(a_dir, "v1")
    b = BuildIndex.scan(b_dir, "v2")
    changes, summary = diff_manifests(a, b)
    assert changes == []
    assert summary["added"] == 0
    assert summary["removed"] == 0
    assert summary["modified"] == 0


def test_diff_detects_added(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"old.js": "old"})
    b = _make_manifest(tmp_path / "b", "v2", {"old.js": "old", "new.js": "new"})
    changes, summary = diff_manifests(a, b)
    added = [c for c in changes if c.status == "added"]
    assert len(added) == 1
    assert added[0].path == "new.js"
    assert summary["added"] == 1


def test_diff_detects_removed(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"keep.js": "k", "gone.js": "g"})
    b = _make_manifest(tmp_path / "b", "v2", {"keep.js": "k"})
    changes, summary = diff_manifests(a, b)
    removed = [c for c in changes if c.status == "removed"]
    assert len(removed) == 1
    assert removed[0].path == "gone.js"
    assert summary["removed"] == 1


def test_diff_detects_modified(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"main.js": "old content"})
    b = _make_manifest(tmp_path / "b", "v2", {"main.js": "new content"})
    changes, summary = diff_manifests(a, b)
    modified = [c for c in changes if c.status == "modified"]
    assert len(modified) == 1
    assert modified[0].path == "main.js"
    assert summary["modified"] == 1


def test_diff_unchanged_not_in_changes(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"same.js": "same"})
    b = _make_manifest(tmp_path / "b", "v2", {"same.js": "same"})
    changes, _ = diff_manifests(a, b)
    assert changes == []


def test_diff_size_delta(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"f.js": "x"})    # 1 byte
    b = _make_manifest(tmp_path / "b", "v2", {"f.js": "xxxxx"})  # 5 bytes
    _, summary = diff_manifests(a, b)
    assert summary["total_size_delta"] == 4


def test_diff_negative_size_delta(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"f.js": "xxxxx"})
    b = _make_manifest(tmp_path / "b", "v2", {"f.js": "x"})
    _, summary = diff_manifests(a, b)
    assert summary["total_size_delta"] == -4


def test_diff_added_file_kind(tmp_path):
    a_dir = tmp_path / "a"; a_dir.mkdir()
    a = BuildIndex.scan(a_dir, "v1")
    b = _make_manifest(tmp_path / "b", "v2", {"img.png": "data"})
    changes, _ = diff_manifests(a, b)
    assert changes[0].kind == "png"


def test_diff_removed_size_a_nonzero(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"big.js": "x" * 100})
    b_dir = tmp_path / "b"; b_dir.mkdir()
    b = BuildIndex.scan(b_dir, "v2")
    changes, _ = diff_manifests(a, b)
    assert changes[0].size_a == 100
    assert changes[0].size_b == 0


def test_diff_added_size_b_nonzero(tmp_path):
    a_dir = tmp_path / "a"; a_dir.mkdir()
    a = BuildIndex.scan(a_dir, "v1")
    b = _make_manifest(tmp_path / "b", "v2", {"new.js": "y" * 50})
    changes, _ = diff_manifests(a, b)
    assert changes[0].size_a == 0
    assert changes[0].size_b == 50


# --- format_text ---

def test_format_text_shows_summary(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"f.js": "old"})
    b = _make_manifest(tmp_path / "b", "v2", {"f.js": "new", "g.js": "new"})
    changes, summary = diff_manifests(a, b)
    text = format_text(changes, summary)
    assert "+1" in text or "1" in text  # added count
    assert "size delta" in text


def test_format_text_caps_at_20(tmp_path):
    files_a = {f"f{i}.js": f"old{i}" for i in range(30)}
    files_b = {f"f{i}.js": f"new{i}" for i in range(30)}
    a = _make_manifest(tmp_path / "a", "v1", files_a)
    b = _make_manifest(tmp_path / "b", "v2", files_b)
    changes, summary = diff_manifests(a, b)
    text = format_text(changes, summary)
    assert "more" in text


def test_format_text_modified_shows_delta(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"m.js": "old"})    # 3B
    b = _make_manifest(tmp_path / "b", "v2", {"m.js": "larger"})  # 6B
    changes, summary = diff_manifests(a, b)
    text = format_text(changes, summary)
    assert "m.js" in text
    assert "+" in text or "-" in text  # delta sign


def test_format_text_added_shows_plus(tmp_path):
    a_dir = tmp_path / "a"; a_dir.mkdir()
    a = BuildIndex.scan(a_dir, "v1")
    b = _make_manifest(tmp_path / "b", "v2", {"new.js": "x"})
    changes, summary = diff_manifests(a, b)
    text = format_text(changes, summary)
    assert "+ new.js" in text or "+  new.js" in text or "new.js" in text


def test_format_text_removed_shows_minus(tmp_path):
    a = _make_manifest(tmp_path / "a", "v1", {"old.js": "x"})
    b_dir = tmp_path / "b"; b_dir.mkdir()
    b = BuildIndex.scan(b_dir, "v2")
    changes, summary = diff_manifests(a, b)
    text = format_text(changes, summary)
    assert "old.js" in text
    assert "-" in text


# --- m11: FileChange has no hash_match field ---

def test_file_change_has_no_hash_match_field(tmp_path):
    """hash_match is dead weight — should be removed from FileChange."""
    a = _make_manifest(tmp_path / "a", "v1", {"f.js": "old"})
    b = _make_manifest(tmp_path / "b", "v2", {"f.js": "new"})
    changes, _ = diff_manifests(a, b)
    assert len(changes) == 1
    assert not hasattr(changes[0], "hash_match"), "hash_match should be removed"
