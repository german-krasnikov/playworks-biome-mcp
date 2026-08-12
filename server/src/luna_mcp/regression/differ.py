"""Pixel diff using Pillow. No numpy needed."""
import io
import pathlib
import re

from PIL import Image, ImageChops, ImageDraw

_MASK_RE = re.compile(r"(\d+),(\d+),(\d+),(\d+)")


def parse_mask_zones(zones: str) -> list:
    """Parse 'x,y,w,h;x,y,w,h;...' into list of (x, y, w, h) tuples."""
    if not zones:
        return []
    out = []
    for part in zones.split(";"):
        m = _MASK_RE.match(part.strip())
        if m:
            out.append(tuple(int(x) for x in m.groups()))
    return out


def _apply_masks(img: Image.Image, masks: list) -> None:
    """Black out masked rectangles in-place."""
    if not masks:
        return
    d = ImageDraw.Draw(img)
    for x, y, w, h in masks:
        d.rectangle([x, y, x + w, y + h], fill=(0, 0, 0))


def diff_pct(baseline_path: pathlib.Path, current_bytes: bytes,
             mask_zones: str = "", noise_threshold: int = 3) -> tuple:
    """Return (pct, error). pct is 0.0–100.0 fraction of changed pixels."""
    a = Image.open(baseline_path).convert("RGB")
    b = Image.open(io.BytesIO(current_bytes)).convert("RGB")
    if a.size != b.size:
        return 0.0, f"size mismatch: baseline={a.size} current={b.size}"
    masks = parse_mask_zones(mask_zones)
    if masks:
        _apply_masks(a, masks)
        _apply_masks(b, masks)
    diff = ImageChops.difference(a, b)
    raw = diff.tobytes()
    px_changed = sum(
        1 for i in range(0, len(raw), 3)
        if max(raw[i], raw[i+1], raw[i+2]) > noise_threshold
    )
    total = a.width * a.height
    return (px_changed / total * 100), None
