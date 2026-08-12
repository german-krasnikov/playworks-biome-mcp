"""Asset catalog — walk dir, classify by extension."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

_KIND_BY_EXT: dict[str, str] = {
    ".png": "texture", ".jpg": "texture", ".jpeg": "texture",
    ".webp": "texture", ".bmp": "texture", ".gif": "texture",
    ".wav": "audio", ".mp3": "audio", ".ogg": "audio", ".m4a": "audio",
    ".ttf": "font", ".otf": "font", ".woff": "font", ".woff2": "font",
    ".obj": "mesh", ".fbx": "mesh", ".glb": "mesh", ".gltf": "mesh",
}


@dataclass(frozen=True)
class Asset:
    path: str       # relative to root
    abs_path: str
    kind: str       # texture|audio|font|mesh|other
    size: int       # bytes


class AssetCatalog:
    def __init__(self, root: pathlib.Path):
        root = pathlib.Path(root)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"not a directory: {root}")
        self._root = root.resolve()

    def scan(self, max_files: int = 1000) -> list[Asset]:
        assets: list[Asset] = []
        # NOTE: rglob follows directory symlinks on Python < 3.12.
        # Caller is responsible for providing trusted paths.
        for p in self._root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(self._root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            try:
                size = p.stat().st_size
                kind = _KIND_BY_EXT.get(p.suffix.lower(), "other")
                assets.append(Asset(path=str(rel), abs_path=str(p), kind=kind, size=size))
                if len(assets) >= max_files:
                    break
            except OSError:
                continue
        return sorted(assets, key=lambda a: a.size, reverse=True)

    def total_size(self, assets: list[Asset]) -> int:
        return sum(a.size for a in assets)

    def by_kind(self, assets: list[Asset]) -> dict[str, list[Asset]]:
        out: dict[str, list[Asset]] = {}
        for a in assets:
            out.setdefault(a.kind, []).append(a)
        return out
