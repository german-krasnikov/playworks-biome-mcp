"""Real-compression probe: run cwebp/pngquant to get ground-truth sizes.

Degrades gracefully: falls back to Pillow in-memory estimate when binaries absent.
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .texture_analyzer import TextureAnalyzer

_LOG = logging.getLogger(__name__)


class CompressionProbe:
    """Subprocess-based compression probe with Pillow fallback."""

    def __init__(self, analyzer: "TextureAnalyzer | None" = None):
        self._analyzer = analyzer

    def probe_webp(self, abs_path: str, quality: int = 80) -> int:
        """Return compressed WEBP size in bytes using cwebp, or Pillow fallback."""
        cwebp = shutil.which("cwebp")
        if not cwebp:
            return self._pillow_fallback(abs_path, quality)

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "out.webp"
            try:
                res = subprocess.run(
                    [cwebp, "-q", str(quality), abs_path, "-o", str(out)],
                    capture_output=True, timeout=30,
                )
                if res.returncode == 0 and out.exists():
                    return out.stat().st_size
            except Exception as e:
                _LOG.debug("probe failed: %s", e)
        return 0

    def probe_png(self, abs_path: str, quality: int = 80) -> int:
        """Return compressed PNG size using pngquant, or 0 when absent."""
        pngquant = shutil.which("pngquant")
        if not pngquant:
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "out.png"
            try:
                res = subprocess.run(
                    [pngquant, "--force", "--output", str(out), abs_path],
                    capture_output=True, timeout=30,
                )
                if res.returncode == 0 and out.exists():
                    return out.stat().st_size
            except Exception as e:
                _LOG.debug("probe failed: %s", e)
        return 0

    def _pillow_fallback(self, abs_path: str, quality: int) -> int:
        if self._analyzer is None:
            return 0
        return self._analyzer.estimate_webp_size(abs_path, quality)
