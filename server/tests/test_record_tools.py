"""Tests for tools/record_tools.py — RED phase."""
import json

import pytest


def _make_tool_module(tmp_path):
    """Import record_tools with a fresh recorder pointing at tmp_path."""
    import luna_mcp.tools.record_tools as rt

    # Reset module-level recorder
    from luna_mcp.record.recorder import Recorder
    rt._recorder = Recorder(tmp_path / "recordings")
    return rt


@pytest.fixture
def rt(tmp_path):
    return _make_tool_module(tmp_path)


@pytest.fixture
def tmp_recordings(tmp_path):
    return tmp_path / "recordings"


@pytest.mark.asyncio
async def test_record_start_returns_path(rt):
    result = await rt.record_start("mysession")
    assert "mysession" in result
    assert "recording" in result.lower() or ".jsonl" in result


@pytest.mark.asyncio
async def test_record_start_already_active_returns_invalid(rt):
    await rt.record_start("first")
    result = await rt.record_start("second")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_record_start_invalid_name(rt):
    result = await rt.record_start("bad name!")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_record_stop_returns_saved_path(rt):
    await rt.record_start("s1")
    result = await rt.record_stop()
    assert "saved" in result.lower() or ".jsonl" in result


@pytest.mark.asyncio
async def test_record_stop_inactive_returns_invalid(rt):
    result = await rt.record_stop()
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_record_list_no_recordings(rt):
    result = await rt.record_list()
    assert "no recordings" in result.lower()


@pytest.mark.asyncio
async def test_record_list_returns_text(rt):
    await rt.record_start("sess1")
    await rt.record_stop()
    await rt.record_start("sess2")
    await rt.record_stop()
    result = await rt.record_list()
    assert "sess1" in result
    assert "sess2" in result


@pytest.mark.asyncio
async def test_replay_unknown_returns_invalid(rt):
    result = await rt.replay("nonexistent")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_replay_existing_calls_dispatch(rt, tmp_path):
    """Create a session file and replay it with a mock dispatch."""
    from luna_mcp.record.fingerprint import hash_result
    from luna_mcp.record.redact import redact_result

    # Write a session manually
    rec_dir = rt._recorder._base
    session_file = rec_dir / "mysess.jsonl"
    header = {"v": 1, "sid": "mysess", "started_at": 1000.0}
    step = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result(redact_result("ping", "pong"))}
    session_file.write_text(json.dumps(header) + "\n" + json.dumps(step) + "\n")

    called = []
    async def mock_dispatch(tool, **kw):
        called.append(tool)
        return "pong"

    rt._dispatch_fn = mock_dispatch
    result = await rt.replay("mysess")
    assert called == ["ping"]
    assert "OK" in result


@pytest.mark.asyncio
async def test_record_diff_missing_files(rt):
    result = await rt.record_diff("a", "b")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_record_diff_two_files(rt, tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    rec_dir = rt._recorder._base
    header = {"v": 1, "sid": "x", "started_at": 1000.0}
    step = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result("pong")}

    (rec_dir / "sess_a.jsonl").write_text(json.dumps(header) + "\n" + json.dumps(step) + "\n")
    (rec_dir / "sess_b.jsonl").write_text(json.dumps(header) + "\n" + json.dumps(step) + "\n")

    result = await rt.record_diff("sess_a", "sess_b")
    assert "OK" in result or "ping" in result
