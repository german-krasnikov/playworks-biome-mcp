"""Set-of-Mark tools: annotated screenshot + marker-based interaction."""
from __future__ import annotations

import io
import pathlib
import uuid
from typing import Callable

from PIL import Image

from ..som.extract import extract_rects
from ..som.overlay import _leaf, annotate
from ..state.marker_map import MarkerMap, Rect
from ..tmp_cleanup import cleanup_old as _cleanup_old_tmp
from ..tmp_cleanup import track as _track_tmp
from . import maybe_expose

# Module-level singleton map (shared across tools)
_marker_map = MarkerMap()


def _parse_rect_lines(text: str) -> list[dict]:
    """Parse 'path|x|y|w|h|kind\\n...' text into list of dicts."""
    rects = []
    for line in text.strip().splitlines():
        parts = line.strip().split("|")
        if len(parts) < 6:
            continue
        try:
            rects.append({
                "path": parts[0],
                "x": int(parts[1]),
                "y": int(parts[2]),
                "w": int(parts[3]),
                "h": int(parts[4]),
                "kind": parts[5],
            })
        except (ValueError, IndexError):
            continue
    return rects


def _build_som_result(png_bytes: bytes, rects: list[dict], marker_map: MarkerMap) -> str:
    """Annotate screenshot, save to /tmp, populate marker_map. Returns path + legend."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img_w, img_h = img.size
    filtered = extract_rects(rects, img_w, img_h)

    annotated, legend_line = annotate(img, filtered)

    _cleanup_old_tmp()
    path = f"/tmp/luna_som_{uuid.uuid4().hex[:8]}.png"
    annotated.save(path, "PNG")
    _track_tmp(pathlib.Path(path))

    # Populate marker map using same indices as overlay (assign_indices → hash-sorted)
    from ..som.extract import assign_indices
    indexed = assign_indices(filtered)
    db_rects = [
        Rect(idx, r["path"], r["x"], r["y"], r["w"], r["h"], r.get("kind", ""))
        for idx, r in indexed
    ]
    marker_map.set(db_rects)

    lines = [path]
    for idx, r in indexed:
        lines.append(f"{idx}={_leaf(r['path'])} ({r.get('kind','?')}) {r['path']}")
    return "\n".join(lines)


def _make_click_marker(marker_map: MarkerMap, click_fn: Callable) -> Callable:
    async def click_marker(marker_id: int) -> str:
        """Click center of marker by id. Resolves to screen (cx,cy) → simulate_click."""
        r = marker_map.get(marker_id)
        if r is None:
            return f"error: marker {marker_id} not found — run screenshot_som first"
        cx = r.x + r.w // 2
        cy = r.y + r.h // 2
        return await click_fn(cx, cy)
    return click_marker


def _make_inspect_marker(marker_map: MarkerMap, diagnose_fn: Callable) -> Callable:
    async def inspect_marker(marker_id: int) -> str:
        """Run diagnose_object on marker's GameObject path."""
        r = marker_map.get(marker_id)
        if r is None:
            return f"error: marker {marker_id} not found — run screenshot_som first"
        return await diagnose_fn(r.path)
    return inspect_marker


def _list_markers_text(marker_map: MarkerMap) -> str:
    rects = marker_map.all()
    if not rects:
        return "(no markers — run screenshot_som first)"
    return "\n".join(f"{r.id} {_leaf(r.path)} ({r.kind})" for r in rects)


def register_som_tools(mcp, call_fn, bridge_getter, click_fn, diagnose_fn, *, exposed: set = frozenset()):
    """Register SoM tools. Returns {name: (fn, params)} for batch."""

    async def screenshot_som(max_marks: int = 20) -> str:
        """Annotated PNG with numbered markers on interactive objects.
        Returns: '/tmp/luna_som_<uid>.png\\n1=InstallBtn (Button) /Canvas/EndCard/Btn\\n...'
        Use marker IDs with click_marker / inspect_marker to avoid sending coordinates."""
        text = await call_fn("collectInteractiveRects", min(max_marks, 40))
        rects = _parse_rect_lines(str(text))
        bridge = bridge_getter()
        png_bytes = await bridge.screenshot()
        return _build_som_result(png_bytes, rects, _marker_map)
    maybe_expose(mcp, screenshot_som, exposed)

    async def list_markers() -> str:
        """Compact list of current markers: '1 InstallBtn (Button)\\n2 Hero (Collider)...'"""
        return _list_markers_text(_marker_map)
    maybe_expose(mcp, list_markers, exposed)

    _click_marker = _make_click_marker(_marker_map, click_fn)
    _click_marker.__name__ = "click_marker"
    _click_marker.__doc__ = "Click center of marker by id. Faster than coordinate-based click."
    maybe_expose(mcp, _click_marker, exposed, name="click_marker")

    _inspect_marker = _make_inspect_marker(_marker_map, diagnose_fn)
    _inspect_marker.__name__ = "inspect_marker"
    _inspect_marker.__doc__ = "Run diagnose_object on marker's GameObject."
    maybe_expose(mcp, _inspect_marker, exposed, name="inspect_marker")

    return {
        "screenshot_som": (screenshot_som, None),
        "list_markers": (list_markers, None),
        "click_marker": (_click_marker, None),
        "inspect_marker": (_inspect_marker, None),
    }
