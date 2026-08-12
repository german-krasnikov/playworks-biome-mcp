from __future__ import annotations

import json
import os
from pathlib import Path


class TypemapResolver:
    """Resolves C# class/method names to JS names via Playworks typemap files."""

    def __init__(self, plugin_path: str | None = None):
        self._plugin_path = plugin_path or os.environ.get("LUNA_PLUGIN_PATH")
        self._by_original: dict[str, list[dict]] = {}  # short name -> [entries]
        self._by_js: dict[str, dict] = {}              # full JS name -> entry
        self._loaded = False

    @property
    def available(self) -> bool:
        return self._typemap_dir is not None

    @property
    def _typemap_dir(self) -> Path | None:
        if not self._plugin_path:
            return None
        d = Path(self._plugin_path) / "pipeline" / "templates" / "LunaCompiler" / "typemaps"
        return d if d.is_dir() else None

    def _load_all(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        d = self._typemap_dir
        if not d:
            return
        for f in sorted(d.glob("*.typemap.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            for cls in data.get("Classes", []):
                orig = cls.get("originalClassName", "")
                js = cls.get("jsClassName", "")
                entry = {
                    "originalClassName": orig,
                    "jsClassName": js,
                    "methods": cls.get("methods", []),
                    "constructors": cls.get("constructors", []),
                }
                self._by_original.setdefault(orig, []).append(entry)
                if js:
                    self._by_js[js] = entry

    def _find_class(self, class_name: str) -> dict | None:
        self._load_all()
        if class_name in self._by_js:
            return self._by_js[class_name]
        entries = self._by_original.get(class_name, [])
        if entries:
            return entries[0]
        if "." in class_name:
            short = class_name.rsplit(".", 1)[-1]
            entries = self._by_original.get(short, [])
            if entries:
                return entries[0]
        return None

    def is_loaded(self) -> bool:
        """Return True if typemap data has been loaded (or attempted)."""
        if not self._loaded:
            self._load_all()
        return bool(self._by_original or self._by_js)

    def known_classes(self) -> list[str]:
        """Return all known original class names."""
        if not self._loaded:
            self._load_all()
        return list(self._by_original.keys())

    def get_js_class_name(self, class_name: str) -> str | None:
        """Return fully-qualified JS class name for a C# class."""
        cls = self._find_class(class_name)
        return cls["jsClassName"] if cls else None

    def resolve_method(self, class_name: str, method_name: str, signature: str = "") -> str | None:
        cls = self._find_class(class_name)
        if not cls:
            return None
        for m in cls["methods"] + cls["constructors"]:
            sig = m["signature"]
            if signature and sig == signature:
                return m["jsName"]
            if not signature and sig.split("(")[0] == method_name:
                return m["jsName"]
        return None

    def get_class_api(self, class_name: str) -> str:
        cls = self._find_class(class_name)
        if not cls:
            return f"Class not found: {class_name}"
        lines = [f"{cls['originalClassName']} (JS: {cls['jsClassName']})"]
        if cls["constructors"]:
            lines.append("CONSTRUCTORS:")
            for c in cls["constructors"]:
                lines.append(f"  {c['signature']} -> {c['jsName']}")
        if cls["methods"]:
            lines.append(f"METHODS ({len(cls['methods'])}):")
            for m in cls["methods"]:
                lines.append(f"  {m['signature']} -> {m['jsName']}")
        return "\n".join(lines)

    def resolve_js_name(self, class_name: str, method_name: str) -> str | None:
        cls = self._find_class(class_name)
        if not cls:
            return None
        js_method = self.resolve_method(class_name, method_name)
        if not js_method:
            return None
        return f"{cls['jsClassName']}.{js_method}"
