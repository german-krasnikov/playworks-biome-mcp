"""Persist Manifests to ~/.playworks-biome-mcp/builds/<label>.json atomically."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import tempfile
from typing import Optional

from .indexer import FileEntry, Manifest


def _to_dict(m: Manifest) -> dict:
    return {
        "label": m.label,
        "root": m.root,
        "total_size": m.total_size,
        "created_at": m.created_at,
        "files": [dataclasses.asdict(f) for f in m.files],
    }


def _from_dict(d: dict) -> Manifest:
    files = [FileEntry(**f) for f in d["files"]]
    return Manifest(
        label=d["label"],
        root=d["root"],
        total_size=d["total_size"],
        files=files,
        created_at=d["created_at"],
    )


class BuildStore:
    def __init__(self, store_dir: pathlib.Path | None = None):
        if store_dir is None:
            from luna_mcp.config import data_dir as _data_dir
            store_dir = _data_dir() / "builds"
        self._dir = pathlib.Path(store_dir)

    def _path(self, label: str) -> pathlib.Path:
        return self._dir / f"{label}.json"

    def save(self, manifest: Manifest) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._path(manifest.label)
        data = json.dumps(_to_dict(manifest), indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            os.write(fd, data.encode())
            os.close(fd)
            os.replace(tmp, target)
        except Exception:
            os.close(fd)
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise

    def load(self, label: str) -> Optional[Manifest]:
        p = self._path(label)
        if not p.exists():
            return None
        try:
            return _from_dict(json.loads(p.read_text()))
        except Exception:
            return None

    def list_all(self) -> list[Manifest]:
        if not self._dir.exists():
            return []
        result = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                result.append(_from_dict(json.loads(p.read_text())))
            except Exception:
                continue
        return result
