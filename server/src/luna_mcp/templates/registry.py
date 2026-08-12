"""Template registry: load, cache, list, save."""
import pathlib
import re
from typing import Optional

from luna_mcp.config import data_dir as _data_dir

_BUNDLED_DIR = pathlib.Path(__file__).resolve().parent / "builtin"
_USER_DIR = _data_dir() / "templates"

_HEADER_RE = re.compile(r'^#\s*(params|desc|version):\s*(.*)$', re.MULTILINE)


class Template:
    def __init__(self, name: str, path: pathlib.Path):
        self.name = name
        self.path = path
        self.body = path.read_text()
        meta = {m.group(1): m.group(2).strip() for m in _HEADER_RE.finditer(self.body)}
        raw_params = meta.get("params", "")
        self.params = [p.strip() for p in raw_params.split(",") if p.strip()]
        self.desc = meta.get("desc", "")
        self.version = meta.get("version", "1")

    def __repr__(self):
        return f"Template({self.name!r}, params={self.params})"


class TemplateRegistry:
    def __init__(self, bundled_dir: pathlib.Path = _BUNDLED_DIR, user_dir: pathlib.Path = _USER_DIR):
        self._bundled_dir = bundled_dir
        self._user_dir = user_dir
        self._cache: dict = {}  # name -> (Template, mtime)

    def load(self, name: str) -> Optional[Template]:
        for d in (self._user_dir, self._bundled_dir):
            p = d / f"{name}.batch"
            if not p.exists():
                continue
            mtime = p.stat().st_mtime
            cached = self._cache.get(name)
            if cached and cached[1] >= mtime:
                return cached[0]
            t = Template(name, p)
            self._cache[name] = (t, mtime)
            return t
        return None

    def list_all(self, filter_str: str = "") -> list:
        seen = {}
        for d in (self._user_dir, self._bundled_dir):
            if not d.exists():
                continue
            for p in sorted(d.glob("*.batch")):
                if p.stem in seen:
                    continue
                if filter_str and filter_str not in p.stem:
                    continue
                t = self.load(p.stem)
                if t:
                    seen[p.stem] = t
        return list(seen.values())

    def save_user(self, name: str, body: str, overwrite: bool = False) -> pathlib.Path:
        if not re.match(r'^[a-z0-9_-]{1,64}$', name):
            raise ValueError(f"invalid template name: {name!r}")
        self._user_dir.mkdir(parents=True, exist_ok=True)
        p = self._user_dir / f"{name}.batch"
        if p.exists() and not overwrite:
            raise FileExistsError(f"{p} exists; pass overwrite=True")
        p.write_text(body)
        self._cache.pop(name, None)
        return p
