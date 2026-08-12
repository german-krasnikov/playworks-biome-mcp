"""Parse and filter rects from Luna collectInteractiveRects output."""
from __future__ import annotations

import hashlib
from typing import Optional

MIN_SIZE = 12  # px


def extract_rects(
    rects: list[dict],
    img_w: int,
    img_h: int,
    top_k: int = 20,
) -> list[dict]:
    """Viewport-cull, min-size filter, sort by area desc, cap at top_k."""
    filtered = []
    for r in rects:
        x, y, w, h = r.get("x", 0), r.get("y", 0), r.get("w", 0), r.get("h", 0)
        if x + w <= 0 or y + h <= 0 or x >= img_w or y >= img_h:
            continue
        if w < MIN_SIZE or h < MIN_SIZE:
            continue
        filtered.append(r)
    filtered.sort(key=lambda r: r.get("w", 0) * r.get("h", 0), reverse=True)
    return filtered[:top_k]


def assign_indices(rects: list[dict], path_pool: Optional[list] = None) -> list[tuple[int, dict]]:
    """Assign stable 1-based indices sorted by hash(path)."""
    _key = lambda p: hashlib.sha256(p.encode()).hexdigest()
    if path_pool is None:
        sorted_rects = sorted(rects, key=lambda r: _key(r.get("path", "")))
        return [(i + 1, r) for i, r in enumerate(sorted_rects)]
    pool_sorted = sorted(set(path_pool), key=_key)
    idx_of = {p: i + 1 for i, p in enumerate(pool_sorted)}
    out = [(idx_of[r.get("path", "")], r) for r in rects if r.get("path", "") in idx_of]
    out.sort(key=lambda t: t[0])
    return out
