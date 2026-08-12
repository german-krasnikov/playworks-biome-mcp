"""Jake -T task discovery with seed catalog fallback."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

_SEED_CATALOG: dict[str, str] = {
    "build": "Build the project",
    "recompile": "Recompile and rebuild",
    "clean": "Remove build artifacts",
    "upload": "Upload to CDN / staging",
}

_JAKE_LINE_RE = re.compile(r'^jake\s+(\S+)\s+#\s*(.+)$')
_TIMEOUT = 15  # seconds


_FALLBACK_KEY = "__fallback__"


def discover_tasks(project_dir: str) -> dict[str, str]:
    """Run 'jake -T' and parse output. Falls back to seed catalog on error.

    When the fallback is used, the returned dict contains ``__fallback__: "1"``
    so the caller can detect the degraded path without content-comparing keys.
    """
    try:
        result = subprocess.run(
            ["jake", "-T"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        parsed = _parse_output(result.stdout)
        if parsed:
            return parsed
        # Empty output → also a fallback situation
        out = _SEED_CATALOG.copy()
        out[_FALLBACK_KEY] = "1"
        return out
    except FileNotFoundError:
        out = _SEED_CATALOG.copy()
        out[_FALLBACK_KEY] = "1"
        return out
    except subprocess.TimeoutExpired:
        return {"error": f"jake -T timed out after {_TIMEOUT}s"}
    except Exception as e:
        return {"error": str(e)}


def _parse_output(stdout: str) -> dict[str, str]:
    tasks: dict[str, str] = {}
    for line in stdout.splitlines():
        m = _JAKE_LINE_RE.match(line.strip())
        if m:
            tasks[m.group(1)] = m.group(2).strip()
    return tasks


def save_catalog(tasks: dict[str, str], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"tasks": tasks}, indent=2))
    import os
    os.replace(str(tmp), str(path))


def load_catalog(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data.get("tasks", {})
    except Exception:
        return {}
