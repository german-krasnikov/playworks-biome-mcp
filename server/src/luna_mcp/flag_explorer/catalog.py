"""JSON-based persistent flag catalog."""
from __future__ import annotations

import json
import os
import pathlib
import time
from dataclasses import asdict, dataclass, field


@dataclass
class FlagEntry:
    name: str
    description: str
    enables: str = ""
    side_effects: list = field(default_factory=list)
    build_size_delta_pct: float = 0.0
    perf_delta: str = ""
    risk: str = "unknown"
    confidence: float = 0.5
    source: str = "user"
    last_updated: float = 0.0


_FIELDS = set(FlagEntry.__dataclass_fields__)


class FlagCatalog:
    def __init__(self, path: pathlib.Path):
        self._path = path
        self._entries: dict[str, FlagEntry] = {}
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
        except Exception:
            return
        for d in data.get("flags", []):
            try:
                clean = {k: v for k, v in d.items() if k in _FIELDS}
                self._entries[d["name"]] = FlagEntry(**clean)
            except Exception:
                continue

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        data = {"version": 1, "flags": [asdict(e) for e in self._entries.values()]}
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self._path))

    def add(self, entry: FlagEntry):
        entry.last_updated = time.time()
        self._entries[entry.name] = entry

    def get(self, name: str) -> FlagEntry | None:
        return self._entries.get(name)

    def all(self) -> list[FlagEntry]:
        return sorted(self._entries.values(), key=lambda e: e.name)

    def find_by_intent(self, keywords: list[str]) -> list[FlagEntry]:
        """Match keywords against description + enables + side_effects (substring)."""
        matches = []
        for e in self._entries.values():
            blob = f"{e.name} {e.description} {e.enables} {' '.join(e.side_effects)}".lower()
            score = sum(1 for kw in keywords if kw.lower() in blob)
            if score > 0:
                matches.append((score, e))
        return [e for _, e in sorted(matches, key=lambda t: -t[0])]
