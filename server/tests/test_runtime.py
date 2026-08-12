from unittest.mock import AsyncMock, Mock

import pytest

from luna_mcp.luna_runtime import LunaRuntime


@pytest.fixture
def mock_bridge():
    bridge = Mock()
    bridge.eval = AsyncMock(return_value="ok")
    return bridge


@pytest.fixture
def runtime(mock_bridge):
    return LunaRuntime(mock_bridge)


# ── inject_helpers ────────────────────────────────────────────────────────────

async def test_inject_helpers_reads_js_file_and_evals(runtime, mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="injected")
    await runtime.inject_helpers()
    mock_bridge.eval.assert_called_once()
    expr = mock_bridge.eval.call_args[0][0]
    assert "__luna_mcp" in expr
    assert "iframe" in expr


async def test_inject_sets_injected_flag_on_success(runtime, mock_bridge):
    # check → need inject, blob inject → injected (2 calls total)
    mock_bridge.eval = AsyncMock(side_effect=["need inject", "injected"])
    assert runtime._injected is False
    await runtime.inject_helpers()
    assert runtime._injected is True


async def test_inject_sets_injected_false_on_failure(runtime, mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="failed")
    await runtime.inject_helpers()
    assert runtime._injected is False


async def test_inject_uses_blob_url_not_base64_chunks(runtime, mock_bridge):
    """New: injection is exactly 2 calls (check + blob), not 5+ with base64 chunks."""
    mock_bridge.eval = AsyncMock(side_effect=["need inject", "injected"])
    await runtime.inject_helpers()
    assert mock_bridge.eval.call_count == 2
    blob_expr = mock_bridge.eval.call_args_list[1][0][0]
    assert "Blob" in blob_expr
    assert "URL.createObjectURL" in blob_expr
    # Should NOT contain base64 patterns
    assert "atob" not in blob_expr
    assert "__luna_mcp_b64" not in blob_expr


# ── ensure_helpers ────────────────────────────────────────────────────────────

async def test_ensure_helpers_skips_inject_if_already_present(runtime, mock_bridge):
    runtime._injected = True
    mock_bridge.eval = AsyncMock(return_value="ok")
    await runtime.ensure_helpers()
    # only the check eval, no inject
    mock_bridge.eval.assert_called_once()
    check_expr = mock_bridge.eval.call_args[0][0]
    assert "__luna_mcp" in check_expr


async def test_ensure_helpers_reinjects_if_missing(runtime, mock_bridge):
    runtime._injected = True
    # check → missing, inject: check → need inject, blob → injected (3 calls total)
    mock_bridge.eval = AsyncMock(side_effect=["missing", "need inject", "injected"])
    await runtime.ensure_helpers()
    assert runtime._injected is True


async def test_ensure_helpers_injects_if_not_injected(runtime, mock_bridge):
    runtime._injected = False
    mock_bridge.eval = AsyncMock(return_value="injected")
    await runtime.ensure_helpers()
    mock_bridge.eval.assert_called_once()
    expr = mock_bridge.eval.call_args[0][0]
    assert "iframe" in expr


# ── call ─────────────────────────────────────────────────────────────────────

async def test_call_invokes_method_in_iframe(runtime, mock_bridge):
    # helpers present path: single combined eval returns result directly
    mock_bridge.eval = AsyncMock(return_value="result")
    result = await runtime.call("ping")
    assert mock_bridge.eval.call_count == 1
    expr = mock_bridge.eval.call_args[0][0]
    assert "__luna_mcp.ping()" in expr
    assert "iframe" in expr
    assert result == "result"


async def test_call_passes_string_args(runtime, mock_bridge):
    mock_bridge.eval = AsyncMock(return_value="tree")
    await runtime.call("getHierarchy", 2, "Player")
    expr = mock_bridge.eval.call_args[0][0]
    assert "__luna_mcp.getHierarchy(2, " in expr
    assert '"Player"' in expr


async def test_call_ensures_helpers_first(runtime, mock_bridge):
    """call() single-eval: the combined expr embeds both the guard and the call."""
    mock_bridge.eval = AsyncMock(return_value="pong")
    await runtime.call("ping")
    assert mock_bridge.eval.call_count == 1
    expr = mock_bridge.eval.call_args[0][0]
    assert "iframe" in expr


# ── NEW: 1-RTT contract ───────────────────────────────────────────────────────

async def test_call_single_eval_when_helpers_present(runtime, mock_bridge):
    """Steady-state: helpers present → exactly 1 bridge.eval call."""
    mock_bridge.eval = AsyncMock(return_value="result")
    result = await runtime.call("ping")
    assert mock_bridge.eval.call_count == 1
    expr = mock_bridge.eval.call_args[0][0]
    assert "__luna_mcp.ping(" in expr
    assert "__LUNA_NEEDS_INJECT__" in expr   # sentinel guard is in the expression
    assert result == "result"


async def test_call_injects_and_retries_on_sentinel(runtime, mock_bridge):
    """Missing helpers: first eval returns sentinel → inject → retry → success."""
    mock_bridge.eval = AsyncMock(side_effect=["__LUNA_NEEDS_INJECT__", "pong"])
    runtime.inject_helpers = AsyncMock()
    result = await runtime.call("ping")
    assert result == "pong"
    assert mock_bridge.eval.call_count == 2
    runtime.inject_helpers.assert_awaited_once()


async def test_call_passes_args_in_combined_expr(runtime, mock_bridge):
    """Args are serialised inside the combined single-eval expression."""
    mock_bridge.eval = AsyncMock(return_value="ok")
    await runtime.call("getHierarchy", 2, "Player")
    expr = mock_bridge.eval.call_args[0][0]
    assert '__luna_mcp.getHierarchy(2, "Player")' in expr


async def test_call_propagates_timeout(runtime, mock_bridge):
    """timeout kwarg is forwarded to bridge.eval."""
    mock_bridge.eval = AsyncMock(return_value="ok")
    await runtime.call("ping", timeout=5.0)
    _, kwargs = mock_bridge.eval.call_args
    assert kwargs.get("timeout") == 5.0


async def test_call_raises_when_sentinel_after_inject(runtime, mock_bridge):
    """If eval returns sentinel both before and after inject, raise RuntimeError."""
    mock_bridge.eval = AsyncMock(return_value="__LUNA_NEEDS_INJECT__")
    runtime.inject_helpers = AsyncMock()
    with pytest.raises(RuntimeError, match="luna helpers unavailable"):
        await runtime.call("ping")
