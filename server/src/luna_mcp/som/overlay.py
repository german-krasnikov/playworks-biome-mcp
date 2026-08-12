"""Pillow-based Set-of-Mark overlay renderer.

Draws numbered circles at top-left of each rect, 2px stroke box,
8-color palette cycling by index. Collision avoidance via diagonal push.
"""
from __future__ import annotations

import re

from PIL import Image, ImageDraw, ImageFont

LABEL_R = 11
STROKE_W = 2
MIN_DIST = LABEL_R * 2

PALETTE = [
    (220, 50,  50),
    (50,  150, 220),
    (50,  200, 80),
    (240, 170, 30),
    (170, 70,  220),
    (30,  210, 200),
    (220, 100, 180),
    (120, 90,  50),
]


def _index_color(index: int) -> tuple[int, int, int]:
    return PALETTE[(index - 1) % len(PALETTE)]


def _load_font(size: int = 14) -> "ImageFont.ImageFont | None":
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _compute_centers(rects: list[dict]) -> list[tuple[int, int]]:
    return [(r.get("x", 0) + LABEL_R, r.get("y", 0) + LABEL_R) for r in rects]


def _resolve_collisions(centers: list[tuple[int, int]], max_iter: int = 16) -> list[tuple[int, int]]:
    pts = list(centers)
    for _ in range(max_iter):
        changed = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                cx1, cy1 = pts[i]
                cx2, cy2 = pts[j]
                dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                if dist < MIN_DIST and dist > 0:
                    dx = (cx1 - cx2) / dist
                    dy = (cy1 - cy2) / dist
                    gap = (MIN_DIST - dist) / 2 + 1
                    pts[i] = (int(cx1 + dx * gap), int(cy1 + dy * gap))
                    pts[j] = (int(cx2 - dx * gap), int(cy2 - dy * gap))
                    changed = True
                elif dist == 0:
                    pts[i] = (cx1 + LABEL_R, cy1 - LABEL_R)
                    pts[j] = (cx2 - LABEL_R, cy2 + LABEL_R)
                    changed = True
        if not changed:
            break
    return pts


_LEAF_STRIP = re.compile(r'[\x00-\x1f"`<>\\{}]')


def _leaf(path: str) -> str:
    leaf = path.rsplit("/", 1)[-1] if "/" in path else path
    leaf = _LEAF_STRIP.sub("", leaf)
    leaf = leaf.replace("Legend:", "")
    return leaf


def annotate(img: Image.Image, rects: list[dict]) -> tuple[Image.Image, str]:
    """Draw numbered overlays on img. Returns (annotated_img, legend).

    Legend format: '1=Btn (Button) 2=Hero (Renderer) ...'
    """
    if not rects:
        return img, "(no marks)"

    from .extract import assign_indices
    indexed = assign_indices(rects)

    draw = ImageDraw.Draw(img)
    font = _load_font(14)

    centers = _compute_centers([r for _, r in indexed])
    centers = _resolve_collisions(centers)

    for (idx, rect), (cx, cy) in zip(indexed, centers):
        color = _index_color(idx)
        x, y, w, h = rect.get("x", 0), rect.get("y", 0), rect.get("w", 0), rect.get("h", 0)
        for s in range(STROKE_W):
            draw.rectangle([x+s, y+s, x+w-s-1, y+h-s-1], outline=color)
        draw.ellipse([cx-LABEL_R, cy-LABEL_R, cx+LABEL_R, cy+LABEL_R], fill=color, outline=(255,255,255))
        label = str(idx)
        try:
            if font is not None:
                try:
                    bbox = font.getbbox(label)
                    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                except AttributeError:
                    tw, th = 8, 10
                draw.text((cx-tw//2, cy-th//2), label, fill=(255,255,255), font=font)
            else:
                draw.text((cx-4, cy-5), label, fill=(255,255,255))
        except Exception:
            pass

    kind_map = {r.get("path", ""): r.get("kind", "") for r in rects}
    legend = " ".join(
        f"{idx}={_leaf(r.get('path','?'))} ({kind_map.get(r.get('path',''), '?')})"
        for idx, r in indexed
    )
    return img, legend
