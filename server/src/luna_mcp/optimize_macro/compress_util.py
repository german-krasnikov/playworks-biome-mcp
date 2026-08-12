"""Brotli wire-size estimation with graceful fallback.

Priority:
  1. Python `brotli` package (in-process, quality=11)
  2. `brotli` CLI binary via subprocess
  3. Heuristic: return raw byte length, label as uncompressed/heuristic
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
import tempfile
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class BrotliBackend(Enum):
    PYTHON = "python"
    BINARY = "binary"
    HEURISTIC = "heuristic"


def wire_size_label(backend: BrotliBackend) -> str:
    if backend == BrotliBackend.HEURISTIC:
        return "uncompressed/heuristic"
    return "brotli-compressed"


def _import_brotli():
    """Return brotli module or None."""
    try:
        return importlib.import_module("brotli")
    except (ImportError, TypeError):
        return None


def _find_brotli_binary() -> Optional[str]:
    """Return path to brotli binary or None."""
    return shutil.which("brotli")


def brotli_compressed_size(data: bytes) -> Tuple[int, BrotliBackend]:
    """Return (compressed_bytes, backend) for the given raw bytes."""
    brotli_mod = _import_brotli()
    if brotli_mod is not None:
        compressed = brotli_mod.compress(data, quality=11)
        return len(compressed), BrotliBackend.PYTHON

    binary = _find_brotli_binary()
    if binary is not None:
        return _compress_via_binary(data, binary)

    return len(data), BrotliBackend.HEURISTIC


def _compress_via_binary(data: bytes, binary: str) -> Tuple[int, BrotliBackend]:
    with tempfile.NamedTemporaryFile(suffix=".br", delete=False) as tmp:
        out_path = tmp.name
    try:
        subprocess.run(
            [binary, "--quality=11", "-o", out_path, "-"],
            input=data,
            capture_output=True,
            check=True,
        )
        size = Path(out_path).stat().st_size
        return size, BrotliBackend.BINARY
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return len(data), BrotliBackend.HEURISTIC
    finally:
        Path(out_path).unlink(missing_ok=True)
