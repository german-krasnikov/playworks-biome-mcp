"""Tests for record/fingerprint.py — RED phase."""
import pytest

from luna_mcp.record.fingerprint import hash_result, scene_fp


@pytest.mark.asyncio
async def test_scene_fp_calls_snapshot_state():
    """scene_fp should call call_fn with 'snapshot_state' and return 16-char hex."""
    calls = []
    async def mock_call(method, *args, **kw):
        calls.append((method, args, kw))
        return "snapshot_data_here"

    result = await scene_fp(mock_call)
    assert len(calls) == 1
    assert calls[0][0] == "snapshotState"
    assert len(result) == 16
    assert all(c in "0123456789abcdef" for c in result)


@pytest.mark.asyncio
async def test_scene_fp_returns_unavailable_on_error():
    async def failing_call(method, *args, **kw):
        raise RuntimeError("CDP error")

    result = await scene_fp(failing_call)
    assert result == "unavailable"


def test_hash_result_stable():
    """Same input → same hash."""
    h1 = hash_result("hello world")
    h2 = hash_result("hello world")
    assert h1 == h2


def test_hash_result_truncates_to_16():
    h = hash_result("any string")
    assert len(h) == 16


def test_hash_result_different_inputs():
    h1 = hash_result("abc")
    h2 = hash_result("xyz")
    assert h1 != h2


def test_hash_result_empty():
    h = hash_result("")
    assert len(h) == 16


def test_hash_result_none_like():
    h = hash_result(None)
    assert len(h) == 16
