"""Static catalog of known PlayCanvas modules with size estimates."""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleInfo:
    id: str
    exports: list[str]
    size_kb: int
    category: str


class ModuleCatalog:
    def __init__(self, data_path: pathlib.Path):
        self._path = data_path
        self._modules: list[ModuleInfo] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for m in data.get("modules", []):
                self._modules.append(ModuleInfo(
                    id=m["id"],
                    exports=m["exports"],
                    size_kb=m["size_kb"],
                    category=m.get("category", "other"),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    def all(self) -> list[ModuleInfo]:
        return list(self._modules)

    def get(self, module_id: str) -> ModuleInfo | None:
        for m in self._modules:
            if m.id == module_id:
                return m
        return None

    def total_kb(self) -> int:
        return sum(m.size_kb for m in self._modules)
