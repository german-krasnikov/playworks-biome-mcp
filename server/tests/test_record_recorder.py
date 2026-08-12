"""Tests for record/recorder.py — RED phase."""
import json

import pytest

from luna_mcp.record.recorder import Recorder


def test_start_creates_jsonl_with_header(tmp_path):
    rec = Recorder(tmp_path / "recs")
    path = rec.start("mysession")
    assert path.exists()
    assert path.suffix == ".jsonl"
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    header = json.loads(lines[0])
    assert header["v"] == 1
    assert header["sid"] == "mysession"
    assert "started_at" in header


def test_start_invalid_name_raises(tmp_path):
    rec = Recorder(tmp_path)
    with pytest.raises(ValueError):
        rec.start("bad name!")


def test_start_invalid_name_slash(tmp_path):
    rec = Recorder(tmp_path)
    with pytest.raises(ValueError):
        rec.start("bad/path")


def test_start_when_active_raises(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("first")
    with pytest.raises(RuntimeError):
        rec.start("second")


def test_log_appends_lines(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("s1")
    rec.log("ping", {}, "pong", 5)
    rec.log("get_hierarchy", {"depth": 2}, "root\n  child", 30)
    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert len(lines) == 3  # header + 2 log entries


def test_log_includes_timestamp_tool_args_summary_hash(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("s2")
    rec.log("ping", {"x": "y"}, "pong", 10)
    lines = (tmp_path / "s2.jsonl").read_text().splitlines()
    entry = json.loads(lines[1])
    assert entry["tool"] == "ping"
    assert "ts" in entry
    assert "args" in entry
    assert "summary" in entry
    assert "hash" in entry
    assert "ms" in entry
    assert entry["ms"] == 10


def test_log_when_inactive_noop(tmp_path):
    rec = Recorder(tmp_path)
    # Not started — log should silently do nothing
    rec.log("ping", {}, "pong", 5)  # no exception


def test_stop_resets_active(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("s3")
    assert rec.active is True
    path = rec.stop()
    assert path is not None
    assert rec.active is False


def test_stop_when_inactive_returns_none(tmp_path):
    rec = Recorder(tmp_path)
    result = rec.stop()
    assert result is None


def test_list_returns_sorted_paths(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("aaa")
    rec.stop()
    rec.start("bbb")
    rec.stop()
    paths = rec.list()
    assert len(paths) == 2
    names = [p.stem for p in paths]
    assert names == sorted(names)


def test_session_id_property(tmp_path):
    rec = Recorder(tmp_path)
    assert rec.session_id is None
    rec.start("mysid")
    assert rec.session_id == "mysid"
    rec.stop()
    assert rec.session_id is None


def test_log_redacts_sensitive_args(tmp_path):
    rec = Recorder(tmp_path)
    rec.start("s4")
    rec.log("some_tool", {"token": "secret123"}, "ok", 5)
    lines = (tmp_path / "s4.jsonl").read_text().splitlines()
    entry = json.loads(lines[1])
    assert entry["args"]["token"] == "***"


def test_base_dir_created_if_missing(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    rec = Recorder(nested)
    assert nested.exists()
