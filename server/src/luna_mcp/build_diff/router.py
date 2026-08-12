"""Tier dispatcher: file → semantic → visual."""
from __future__ import annotations

import pathlib
from typing import Awaitable, Callable, Optional

from .file_diff import diff_manifests, format_text
from .indexer import _TEXT_KINDS, Manifest


class TierRouter:
    def __init__(self, semantic_diff, visual_fn: Callable[..., Awaitable[Optional[float]]]):
        self._semantic = semantic_diff
        self._visual = visual_fn

    async def diff(self, a: Manifest, b: Manifest, mode: str = "auto") -> str:
        changes, summary = diff_manifests(a, b)
        out = [f"=== build_diff: {a.label} → {b.label} ===", format_text(changes, summary)]

        if mode == "file":
            return "\n".join(out)

        if mode in ("semantic", "auto") and self._semantic:
            semantic_lines = []
            for c in changes:
                if c.status != "modified" or c.kind not in _TEXT_KINDS:
                    continue
                pa = pathlib.Path(a.root) / c.path
                pb = pathlib.Path(b.root) / c.path
                s = await self._semantic.diff_text_file(pa, pb, c.path)
                if s:
                    semantic_lines.append(f"  {c.path}: {s}")
                if len(semantic_lines) >= 5:
                    semantic_lines.append("  ... (more files truncated for budget)")
                    break
            if semantic_lines:
                out.append("\n=== semantic ===")
                out.extend(semantic_lines)

        if mode in ("visual", "auto"):
            visual_lines = []
            for c in changes:
                if c.status != "modified" or c.kind != "png":
                    continue
                pa = pathlib.Path(a.root) / c.path
                pb = pathlib.Path(b.root) / c.path
                pct = await self._visual(pa, pb)
                if pct is not None and pct > 0.5:
                    visual_lines.append(f"  {c.path}: {pct:.1f}% pixels differ")
            if visual_lines:
                out.append("\n=== visual ===")
                out.extend(visual_lines[:5])

        return "\n".join(out)
