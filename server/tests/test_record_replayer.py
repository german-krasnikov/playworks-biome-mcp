"""Tests for record/replayer.py — RED phase."""
import json
import pathlib

import pytest

from luna_mcp.record.replayer import Replayer


def _make_session(path: pathlib.Path, steps: list[dict], name: str = "test") -> pathlib.Path:
    """Write a minimal JSONL session file."""
    file = path / f"{name}.jsonl"
    header = {"v": 1, "sid": name, "started_at": 1000.0}
    lines = [json.dumps(header)]
    for step in steps:
        lines.append(json.dumps(step))
    file.write_text("\n".join(lines) + "\n")
    return file


async def _dispatch_ok(tool, **kw):
    return "pong" if tool == "ping" else "result"


@pytest.mark.asyncio
async def test_replay_missing_file_returns_error(tmp_path):
    r = Replayer(_dispatch_ok)
    report = await r.replay(tmp_path / "missing.jsonl")
    assert report.diverged_at == -1  # header flag
    assert "not found" in report.divergence_reason.lower()


@pytest.mark.asyncio
async def test_replay_dry_run_does_not_call_dispatch(tmp_path):
    called = []
    async def recording_dispatch(tool, **kw):
        called.append(tool)
        return "ok"

    from luna_mcp.record.fingerprint import hash_result
    from luna_mcp.record.redact import redact_result
    step = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result(redact_result("ping", "pong"))}
    f = _make_session(tmp_path, [step])
    r = Replayer(recording_dispatch)
    report = await r.replay(f, dry_run=True)
    assert len(called) == 0
    assert report.ok_steps == 1
    assert "DRY" in report.summary[0]


@pytest.mark.asyncio
async def test_replay_all_match_returns_ok(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    from luna_mcp.record.redact import redact_result

    steps = []
    for tool, result in [("ping", "pong"), ("get_hierarchy", "root\n  child")]:
        steps.append({
            "tool": tool, "args": {},
            "summary": redact_result(tool, result)[:200],
            "hash": hash_result(redact_result(tool, result)),
        })
    f = _make_session(tmp_path, steps)

    async def dispatch(tool, **kw):
        return "pong" if tool == "ping" else "root\n  child"

    r = Replayer(dispatch)
    report = await r.replay(f)
    assert report.diverged_at == -1
    assert report.ok_steps == 2
    assert report.total == 2


@pytest.mark.asyncio
async def test_replay_hash_mismatch_diverges(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    step = {
        "tool": "ping", "args": {},
        "summary": "pong",
        "hash": hash_result("pong"),
    }
    f = _make_session(tmp_path, [step])

    async def dispatch(tool, **kw):
        return "different_result_that_is_completely_different_and_long_enough"

    r = Replayer(dispatch)
    report = await r.replay(f)
    assert report.diverged_at == 1
    assert "hash mismatch" in report.divergence_reason


@pytest.mark.asyncio
async def test_replay_soft_ok_when_summary_matches(tmp_path):
    """Different hash but first 50 chars of summary match → SOFT-OK."""
    from luna_mcp.record.fingerprint import hash_result
    # Step has one hash but dispatch returns something that produces different hash
    # but same summary prefix (first 50 chars)
    prefix = "root\n  child\n  " + "z" * 40  # 55 chars so [:50] matches for both
    old_result = prefix + "x" * 50
    new_result = prefix + "y" * 50  # same first 50 chars of summary, different hash

    from luna_mcp.record.redact import redact_result
    step = {
        "tool": "get_hierarchy", "args": {},
        "summary": redact_result("get_hierarchy", old_result)[:200],
        "hash": hash_result(redact_result("get_hierarchy", old_result)),
    }
    f = _make_session(tmp_path, [step])

    async def dispatch(tool, **kw):
        return new_result

    r = Replayer(dispatch)
    report = await r.replay(f)
    assert report.diverged_at == -1  # SOFT-OK, not diverged
    assert report.ok_steps == 1
    assert "SOFT-OK" in report.summary[0]


@pytest.mark.asyncio
async def test_replay_dispatch_failure_diverges(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    step = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result("pong")}
    f = _make_session(tmp_path, [step])

    async def dispatch(tool, **kw):
        raise RuntimeError("connection lost")

    r = Replayer(dispatch)
    report = await r.replay(f)
    assert report.diverged_at == 1
    assert "call failed" in report.divergence_reason


@pytest.mark.asyncio
async def test_diff_step_ordering(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    step = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result("pong")}
    f1 = _make_session(tmp_path, [step], name="a")
    f2 = _make_session(tmp_path, [step], name="b")
    r = Replayer(_dispatch_ok)
    result = await r.diff(f1, f2)
    assert "[1 OK]" in result
    assert "ping" in result


@pytest.mark.asyncio
async def test_diff_tool_difference(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    step_a = {"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result("pong")}
    step_b = {"tool": "get_hierarchy", "args": {}, "summary": "root", "hash": hash_result("root")}
    f1 = _make_session(tmp_path, [step_a], name="a")
    f2 = _make_session(tmp_path, [step_b], name="b")
    r = Replayer(_dispatch_ok)
    result = await r.diff(f1, f2)
    assert "TOOL-DIV" in result
    assert "ping" in result
    assert "get_hierarchy" in result


@pytest.mark.asyncio
async def test_diff_caps_output_at_100(tmp_path):
    from luna_mcp.record.fingerprint import hash_result
    steps = [{"tool": "ping", "args": {}, "summary": "pong", "hash": hash_result("pong")} for _ in range(150)]
    f1 = _make_session(tmp_path, steps, name="a")
    f2 = _make_session(tmp_path, steps, name="b")
    r = Replayer(_dispatch_ok)
    result = await r.diff(f1, f2)
    # Output lines capped at 100
    assert len(result.splitlines()) <= 100
