"""Diff two config.json files; return plain-text summary."""
from __future__ import annotations

import pathlib

from .reader import read_config


def diff_configs(path_a: pathlib.Path, path_b: pathlib.Path) -> str:
    """Compare two config files; return human-readable diff text."""
    a = read_config(path_a)
    b = read_config(path_b)

    all_keys = set(a.keys()) | set(b.keys())
    added = sorted(k for k in all_keys if k not in a)
    removed = sorted(k for k in all_keys if k not in b)
    changed = sorted(k for k in all_keys if k in a and k in b and a[k] != b[k])

    if not added and not removed and not changed:
        return "identical"

    lines: list[str] = []
    for k in added:
        lines.append(f"+ {k}: {b[k]!r}")
    for k in removed:
        lines.append(f"- {k}: {a[k]!r}")
    for k in changed:
        lines.append(f"~ {k}: {a[k]!r} -> {b[k]!r}")
    return "\n".join(lines)
