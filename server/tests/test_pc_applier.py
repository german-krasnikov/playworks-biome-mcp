"""Tests for pc_replacer.applier — RED phase."""
import pytest

from luna_mcp.pc_replacer.applier import StubApplier


@pytest.mark.asyncio
async def test_stub_module_calls_eval():
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "stubbed:test"

    applier = StubApplier(fake_eval)
    result = await applier.stub_module("test", ["pc.X"])
    assert "stubbed: test" in result
    assert len(captured) == 1
    assert "__pc_replacer_backup" in captured[0]


@pytest.mark.asyncio
async def test_stub_module_multiple_exports():
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'stubbed:mod'"

    applier = StubApplier(fake_eval)
    result = await applier.stub_module("mod", ["pc.A", "pc.B", "pc.C"])
    assert "stubbed: mod" in result
    assert "3 exports" in result


@pytest.mark.asyncio
async def test_stub_module_eval_error():
    async def bad_eval(expr):
        raise RuntimeError("CDP down")

    applier = StubApplier(bad_eval)
    result = await applier.stub_module("x", ["pc.X"])
    assert "[ERROR" in result


@pytest.mark.asyncio
async def test_revert_module_calls_eval():
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'reverted:mod'"

    applier = StubApplier(fake_eval)
    result = await applier.revert_module("mod", ["pc.X"])
    assert "reverted: mod" in result
    assert len(captured) == 1
    assert "__pc_replacer_backup" in captured[0]


@pytest.mark.asyncio
async def test_revert_module_eval_error():
    async def bad_eval(expr):
        raise RuntimeError("CDP down")

    applier = StubApplier(bad_eval)
    result = await applier.revert_module("x", ["pc.X"])
    assert "[ERROR" in result


@pytest.mark.asyncio
async def test_stub_js_contains_backup_guard():
    """The JS must guard against double-backup."""
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    await applier.stub_module("mod", ["pc.X"])
    js = captured[0]
    # Should guard: only backup if not already backed up
    assert "pc_replacer_backup" in js
    assert "pc.X" in js


@pytest.mark.asyncio
async def test_revert_js_restores_and_deletes():
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    await applier.revert_module("mod", ["pc.X"])
    js = captured[0]
    assert "pc.X" in js
    assert "delete" in js


# --- M2: regex validation guards ---

@pytest.mark.asyncio
async def test_stub_rejects_unsafe_module_id():
    """M2: module_id with unsafe chars should return [INVALID...]."""
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    result = await applier.stub_module("../../evil; rm -rf /", ["pc.X"])
    assert "[INVALID" in result
    assert len(captured) == 0  # eval must NOT be called


@pytest.mark.asyncio
async def test_stub_rejects_unsafe_export():
    """M2: export with unsafe chars (e.g. semicolon) should return [INVALID...]."""
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    result = await applier.stub_module("safe-id", ["pc.X; alert(1)"])
    assert "[INVALID" in result
    assert len(captured) == 0


@pytest.mark.asyncio
async def test_revert_rejects_unsafe_module_id():
    """M2: revert_module also validates module_id."""
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    result = await applier.revert_module("../bad", ["pc.X"])
    assert "[INVALID" in result
    assert len(captured) == 0


@pytest.mark.asyncio
async def test_revert_rejects_unsafe_export():
    """revert_module must validate export names — unsafe chars must not reach eval."""
    captured = []

    async def fake_eval(expr):
        captured.append(expr)
        return "'ok'"

    applier = StubApplier(fake_eval)
    result = await applier.revert_module("safe-id", ["pc.X; alert(1)"])
    assert "[INVALID" in result
    assert len(captured) == 0  # eval must NOT be called with injected JS
