"""Texture analyzer — Pillow histogram + entropy + classification."""
from __future__ import annotations

import math
from dataclasses import dataclass

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


@dataclass
class TextureInfo:
    path: str
    width: int = 0
    height: int = 0
    has_alpha: bool = False
    entropy: float = 0.0
    classification: str = "unknown"
    pixels: int = 0


class TextureAnalyzer:
    def analyze(self, abs_path: str) -> TextureInfo:
        info = TextureInfo(path=abs_path)
        if not _PIL_AVAILABLE:
            return info
        try:
            with Image.open(abs_path) as img:
                info.width, info.height = img.size
                info.pixels = info.width * info.height
                info.has_alpha = img.mode in ("RGBA", "LA") or "A" in img.mode
                histogram = img.convert("L").histogram()
                total = sum(histogram)
                if total > 0:
                    entropy = -sum((c / total) * math.log2(c / total) for c in histogram if c > 0)
                    info.entropy = max(0.0, entropy)
            info.classification = self._classify(info)
        except Exception:
            pass
        return info

    def estimate_webp_size(self, abs_path: str, quality: int = 80) -> int:
        """In-process WEBP encode to memory buffer; returns byte count.

        Returns 0 when PIL unavailable or file unreadable.
        """
        if not _PIL_AVAILABLE:
            return 0
        try:
            import io
            with Image.open(abs_path) as img:
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=quality)
                return buf.tell()
        except Exception:
            return 0

    def _classify(self, info: TextureInfo) -> str:
        if info.pixels <= 4096:         # <= 64x64
            return "glyph" if info.has_alpha else "ui"
        if info.entropy > 7.0 and info.pixels > 65536:
            return "photo"
        if info.has_alpha:
            return "sprite"
        return "ui"
