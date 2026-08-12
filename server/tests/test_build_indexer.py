"""Tests for build_diff/indexer.py — RED phase."""
import pathlib
import time

import pytest

from luna_mcp.build_diff.indexer import _TS_RE, BuildIndex, FileEntry

# --- classify ---

def test_classify_js():
    assert BuildIndex.classify(pathlib.Path("foo.js")) == "js"


def test_classify_json():
    assert BuildIndex.classify(pathlib.Path("data.json")) == "json"


def test_classify_png():
    assert BuildIndex.classify(pathlib.Path("img.png")) == "png"


def test_classify_jpg_as_png():
    assert BuildIndex.classify(pathlib.Path("img.jpg")) == "png"


def test_classify_wasm():
    assert BuildIndex.classify(pathlib.Path("engine.wasm")) == "wasm"


def test_classify_unknown_as_other():
    assert BuildIndex.classify(pathlib.Path("foo.unknown")) == "other"


def test_classify_uppercase_ext():
    assert BuildIndex.classify(pathlib.Path("IMG.PNG")) == "png"


# --- hash_file ---

def test_hash_file_text_strips_timestamps(tmp_path):
    a = tmp_path / "a.js"
    b = tmp_path / "b.js"
    a.write_text("/* 1234567890 */\nconsole.log('a')")
    b.write_text("/* 9876543210 */\nconsole.log('a')")
    assert BuildIndex.hash_file(a, "js") == BuildIndex.hash_file(b, "js")


def test_hash_file_json_strips_timestamps(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"timestamp": 1234567890, "val": 1}')
    b.write_text('{"timestamp": 9999999999, "val": 1}')
    assert BuildIndex.hash_file(a, "json") == BuildIndex.hash_file(b, "json")


def test_hash_file_different_content_different_hash(tmp_path):
    a = tmp_path / "a.js"
    b = tmp_path / "b.js"
    a.write_text("console.log('a')")
    b.write_text("console.log('b')")
    assert BuildIndex.hash_file(a, "js") != BuildIndex.hash_file(b, "js")


def test_hash_file_binary_raw(tmp_path):
    a = tmp_path / "a.wasm"
    b = tmp_path / "b.wasm"
    a.write_bytes(b"\x00\x01\x02")
    b.write_bytes(b"\x00\x01\x02")
    assert BuildIndex.hash_file(a, "wasm") == BuildIndex.hash_file(b, "wasm")


def test_hash_file_16_char_hex(tmp_path):
    f = tmp_path / "f.js"
    f.write_text("hello")
    h = BuildIndex.hash_file(f, "js")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


# --- scan ---

def test_scan_single_file(tmp_path):
    (tmp_path / "main.js").write_text("hello")
    m = BuildIndex.scan(tmp_path, "v1")
    assert m.label == "v1"
    assert len(m.files) == 1
    assert m.files[0].path == "main.js"
    assert m.files[0].kind == "js"


def test_scan_multiple_files_sorted(tmp_path):
    (tmp_path / "z.js").write_text("z")
    (tmp_path / "a.json").write_text("{}")
    m = BuildIndex.scan(tmp_path, "v1")
    paths = [f.path for f in m.files]
    assert paths == sorted(paths)


def test_scan_total_size(tmp_path):
    (tmp_path / "a.js").write_text("hello")   # 5 bytes
    (tmp_path / "b.json").write_text('{"x":1}')  # 7 bytes
    m = BuildIndex.scan(tmp_path, "v1")
    assert m.total_size == 12


def test_scan_skips_dotfiles(tmp_path):
    (tmp_path / ".gitignore").write_text("*.pyc")
    (tmp_path / "main.js").write_text("ok")
    m = BuildIndex.scan(tmp_path, "v1")
    paths = [f.path for f in m.files]
    assert ".gitignore" not in paths
    assert "main.js" in paths


def test_scan_subdirectories(tmp_path):
    sub = tmp_path / "assets"
    sub.mkdir()
    (sub / "img.png").write_bytes(b"\x89PNG")
    m = BuildIndex.scan(tmp_path, "v1")
    paths = [f.path for f in m.files]
    assert any("img.png" in p for p in paths)


def test_scan_raises_for_nonexistent(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        BuildIndex.scan(tmp_path / "nope", "v1")


def test_scan_raises_for_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        BuildIndex.scan(f, "v1")


def test_scan_created_at_recent(tmp_path):
    (tmp_path / "x.js").write_text("x")
    before = time.time()
    m = BuildIndex.scan(tmp_path, "v1")
    after = time.time()
    assert before <= m.created_at <= after


def test_scan_root_is_absolute(tmp_path):
    (tmp_path / "x.js").write_text("x")
    m = BuildIndex.scan(tmp_path, "v1")
    assert pathlib.Path(m.root).is_absolute()


# --- FileEntry frozen ---

def test_file_entry_immutable():
    e = FileEntry(path="a.js", size=5, sha256="abc", kind="js")
    with pytest.raises(Exception):
        e.path = "b.js"  # type: ignore


# --- timestamp regex ---

def test_ts_re_strips_block_comment():
    assert _TS_RE.sub("", "/* 1234567890 */") == ""


def test_ts_re_strips_line_comment():
    assert _TS_RE.sub("", "// 1234567890") == ""


def test_ts_re_strips_json_timestamp():
    result = _TS_RE.sub("", '"timestamp": 1234567890')
    assert "1234567890" not in result


# --- M2: hash errors are unique per path ---

def test_hash_errors_are_unique_per_path(tmp_path):
    """Unreadable files get path-derived sentinel, not the same 'ERROR' string."""
    p1 = tmp_path / "file1.js"
    p2 = tmp_path / "file2.js"
    # Don't create the files — hash_file must handle missing files
    h1 = BuildIndex.hash_file(p1, "js")
    h2 = BuildIndex.hash_file(p2, "js")
    assert h1 != h2, "Error hashes must be unique per path"
    assert h1 != "ERROR"
    assert h2 != "ERROR"


# --- M3: hash normalizes buildTime and other timestamp fields ---

def test_hash_normalizes_buildTime_field(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"buildTime": 1000000001, "val": 1}')
    b.write_text('{"buildTime": 9999999999, "val": 1}')
    assert BuildIndex.hash_file(a, "json") == BuildIndex.hash_file(b, "json")


def test_hash_normalizes_generatedAt_field(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"generatedAt": 1000000001, "val": 2}')
    b.write_text('{"generatedAt": 9999999999, "val": 2}')
    assert BuildIndex.hash_file(a, "json") == BuildIndex.hash_file(b, "json")


def test_hash_normalizes_iso_date_string(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"builtAt": "2024-01-01T00:00:00Z", "v": 3}')
    b.write_text('{"builtAt": "2025-12-31T23:59:59Z", "v": 3}')
    assert BuildIndex.hash_file(a, "json") == BuildIndex.hash_file(b, "json")


# --- m9: scan skips dotfile subdirectories ---

def test_scan_skips_dotfile_subdirectories(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")
    (tmp_path / "main.js").write_text("hello")
    m = BuildIndex.scan(tmp_path, "v1")
    paths = [f.path for f in m.files]
    assert "main.js" in paths
    assert not any(".git" in p for p in paths)
