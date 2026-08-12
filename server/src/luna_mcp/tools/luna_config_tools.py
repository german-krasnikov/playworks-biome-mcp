"""MCP tools for Luna config.json get/set/diff + headless jake driver (C4)."""
from __future__ import annotations

import json
import pathlib

from ..luna_config.differ import diff_configs
from ..luna_config.jake_driver import JakeDriver
from ..luna_config.locator import find_config
from ..luna_config.reader import read_config
from ..luna_config.writer import write_config
from ..tools import maybe_expose


async def luna_config_get(config_path: str = "") -> str:
    """Read Luna's config.json and return its contents as text."""
    path = _resolve_path(config_path)
    if path is None:
        return "[INVALID: config.json not found. Set LUNA_PLUGIN_PATH or pass config_path]"
    try:
        data = read_config(path)
    except ValueError as e:
        return f"[INVALID: {e}]"
    lines = [f"config={path}", "---"]
    for k, v in sorted(data.items()):
        lines.append(f"{k}: {v!r}")
    return "\n".join(lines)


async def luna_config_diff(path_a: str, path_b: str) -> str:
    """Diff two config.json files and return a human-readable summary."""
    pa = pathlib.Path(path_a).expanduser().resolve()
    pb = pathlib.Path(path_b).expanduser().resolve()
    if not pa.exists():
        return f"[INVALID: file not found: {pa}]"
    if not pb.exists():
        return f"[INVALID: file not found: {pb}]"
    try:
        return diff_configs(pa, pb)
    except ValueError as e:
        return f"[INVALID: {e}]"


async def luna_config_set(config_json: str, config_path: str = "") -> str:
    """Write new config.json content (batch-only mutation). Validates JSON first."""
    try:
        data = json.loads(config_json)
    except json.JSONDecodeError as e:
        return f"[INVALID: bad JSON — {e}]"
    if not isinstance(data, dict):
        return "[INVALID: config must be a JSON object (dict)]"
    path = _resolve_path(config_path)
    if path is None:
        return "[INVALID: config.json not found. Set LUNA_PLUGIN_PATH or pass config_path]"
    try:
        write_config(path, data)
    except Exception as e:
        return f"[ERROR: {e}]"
    return f"ok: written {len(data)} keys to {path}"


async def jake_build(
    project_path: str = ".",
    execute: bool = False,
) -> str:
    """Construct (and optionally run) the headless jake build command.

    DRY-RUN by default — returns the command + validation.
    Pass execute=True to actually invoke subprocess.
    """
    driver = JakeDriver(project_path=project_path)
    result = driver.build(dry_run=not execute, execute=execute)

    if result.get("error"):
        return f"[ERROR: {result['error']}]"
    if result.get("dry_run"):
        valid = result.get("valid", True)
        status = "valid" if valid else f"invalid ({result.get('error')})"
        return (
            f"DRY_RUN: {result['command']}\n"
            f"project_path={result['project_path']}\n"
            f"validation={status}"
        )
    return (
        f"executed: {result['command']}\n"
        f"returncode={result.get('returncode')}\n"
        f"stdout={result.get('stdout', '')[:500]}\n"
        f"stderr={result.get('stderr', '')[:200]}"
    )


def _resolve_path(config_path: str) -> pathlib.Path | None:
    if config_path:
        p = pathlib.Path(config_path).expanduser().resolve()
        return p if p.exists() else None
    return find_config()


def register_luna_config_tools(mcp, *, exposed: set = frozenset()) -> dict:
    fns = [
        ("luna_config_get",  luna_config_get,  True),
        ("luna_config_diff", luna_config_diff, True),
        ("luna_config_set",  luna_config_set,  False),
        ("jake_build",       jake_build,       False),
    ]
    out = {}
    for name, fn, read_only in fns:
        maybe_expose(mcp, fn, exposed, name=name, read_only=read_only)
        out[name] = (fn, None)
    return out
