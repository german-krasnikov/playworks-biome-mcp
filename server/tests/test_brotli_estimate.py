"""TDD tests for brotli wire-size estimation (C1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from luna_mcp.optimize_macro.compress_util import (
    BrotliBackend,
    brotli_compressed_size,
    wire_size_label,
)

# ── backend detection ──────────────────────────────────────────────────────────

def test_backend_enum_values():
    assert BrotliBackend.PYTHON.value == "python"
    assert BrotliBackend.BINARY.value == "binary"
    assert BrotliBackend.HEURISTIC.value == "heuristic"


def test_wire_size_label_python():
    assert wire_size_label(BrotliBackend.PYTHON) == "brotli-compressed"


def test_wire_size_label_binary():
    assert wire_size_label(BrotliBackend.BINARY) == "brotli-compressed"


def test_wire_size_label_heuristic():
    assert wire_size_label(BrotliBackend.HEURISTIC) == "uncompressed/heuristic"


# ── python brotli package ─────────────────────────────────────────────────────

def test_uses_python_brotli_when_available():
    """When brotli package importable, use it."""
    fake_brotli = MagicMock()
    fake_brotli.compress.return_value = b"x" * 42
    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=fake_brotli):
        size, backend = brotli_compressed_size(b"hello world " * 100)
    assert size == 42
    assert backend == BrotliBackend.PYTHON
    fake_brotli.compress.assert_called_once()


def test_python_brotli_called_with_quality_11():
    """Default quality=11 for ground-truth match."""
    fake_brotli = MagicMock()
    fake_brotli.compress.return_value = b"z" * 20
    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=fake_brotli):
        brotli_compressed_size(b"data")
    _, kwargs = fake_brotli.compress.call_args
    assert kwargs.get("quality") == 11


# ── subprocess binary ─────────────────────────────────────────────────────────

def test_uses_binary_when_python_unavailable():
    """Falls back to brotli binary via subprocess when package missing."""
    from pathlib import Path

    def fake_run(cmd, **kwargs):
        r = MagicMock()
        r.returncode = 0
        for i, part in enumerate(cmd):
            if part == "-o" and i + 1 < len(cmd):
                Path(cmd[i + 1]).write_bytes(b"y" * 55)
                break
        return r

    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=None):
        with patch("luna_mcp.optimize_macro.compress_util._find_brotli_binary", return_value="/usr/bin/brotli"):
            with patch("subprocess.run", side_effect=fake_run):
                size, backend = brotli_compressed_size(b"hello " * 200)
    assert size == 55
    assert backend == BrotliBackend.BINARY


def test_binary_backend_writes_stdin():
    """Binary path pipes data through subprocess stdin."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b""

    import pathlib
    call_args_holder = {}

    def capturing_run(cmd, **kwargs):
        call_args_holder["cmd"] = cmd
        call_args_holder["input"] = kwargs.get("input")
        # write a fake output
        for i, part in enumerate(cmd):
            if part == "-o" and i + 1 < len(cmd):
                pathlib.Path(cmd[i + 1]).write_bytes(b"z" * 30)
                break
        return mock_result

    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=None):
        with patch("luna_mcp.optimize_macro.compress_util._find_brotli_binary", return_value="/usr/bin/brotli"):
            with patch("subprocess.run", side_effect=capturing_run):
                size, backend = brotli_compressed_size(b"test data " * 50)

    assert backend == BrotliBackend.BINARY
    assert b"test data" in call_args_holder["input"]


# ── heuristic fallback ────────────────────────────────────────────────────────

def test_heuristic_fallback_when_nothing_available():
    """Returns raw size with heuristic backend when neither package nor binary present."""
    data = b"A" * 1000
    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=None):
        with patch("luna_mcp.optimize_macro.compress_util._find_brotli_binary", return_value=None):
            size, backend = brotli_compressed_size(data)
    assert backend == BrotliBackend.HEURISTIC
    assert size == len(data)  # raw bytes returned as-is


def test_heuristic_returns_raw_length():
    data = b"X" * 4096
    with patch("luna_mcp.optimize_macro.compress_util._import_brotli", return_value=None):
        with patch("luna_mcp.optimize_macro.compress_util._find_brotli_binary", return_value=None):
            size, backend = brotli_compressed_size(data)
    assert size == 4096


# ── estimator integration ─────────────────────────────────────────────────────

def test_estimator_source_has_wire_size_fields():
    """OptimizationSource should carry wire_size_kb + wire_label."""
    from luna_mcp.optimize_macro.estimator import OptimizationSource
    s = OptimizationSource("assets", 100, 3, "compress", wire_size_kb=62, wire_label="brotli-compressed")
    assert s.wire_size_kb == 62
    assert s.wire_label == "brotli-compressed"


def test_estimator_source_wire_defaults_to_none():
    """Existing code with no wire fields still works (backward compat)."""
    from luna_mcp.optimize_macro.estimator import OptimizationSource
    s = OptimizationSource("jakefile", 50, 1, "x")
    assert s.wire_size_kb is None
    assert s.wire_label is None


def test_combined_plan_to_text_includes_wire_size():
    """to_text shows brotli wire size when available."""
    from luna_mcp.optimize_macro.estimator import CombinedPlan, OptimizationSource
    plan = CombinedPlan(target_kb=200)
    plan.sources.append(
        OptimizationSource("assets", 100, 2, "compress JPEG",
                           wire_size_kb=62, wire_label="brotli-compressed")
    )
    text = plan.to_text()
    assert "brotli-compressed" in text
    assert "62kb" in text


def test_combined_plan_to_text_no_wire_size_unchanged():
    """to_text stays backward-compatible when wire_size_kb is None."""
    from luna_mcp.optimize_macro.estimator import CombinedPlan, OptimizationSource
    plan = CombinedPlan(target_kb=200)
    plan.sources.append(OptimizationSource("jakefile", 50, 1, "strip unused"))
    text = plan.to_text()
    assert "brotli" not in text
    assert "heuristic" not in text
