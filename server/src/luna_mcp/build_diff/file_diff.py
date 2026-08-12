"""Bytes-level set-diff between two Manifests."""
from __future__ import annotations

from dataclasses import dataclass

from .indexer import Manifest


@dataclass
class FileChange:
    path: str
    kind: str
    status: str     # added|removed|modified
    size_a: int
    size_b: int


def diff_manifests(a: Manifest, b: Manifest) -> tuple[list[FileChange], dict]:
    """Returns (changes, summary). Unchanged files are excluded."""
    by_a = {f.path: f for f in a.files}
    by_b = {f.path: f for f in b.files}
    all_paths = sorted(set(by_a) | set(by_b))
    changes = []
    for p in all_paths:
        fa = by_a.get(p)
        fb = by_b.get(p)
        if fa and not fb:
            changes.append(FileChange(p, fa.kind, "removed", fa.size, 0))
        elif fb and not fa:
            changes.append(FileChange(p, fb.kind, "added", 0, fb.size))
        elif fa.sha256 != fb.sha256 or fa.size != fb.size:
            changes.append(FileChange(p, fb.kind, "modified", fa.size, fb.size))
    summary = {
        "added":            sum(1 for c in changes if c.status == "added"),
        "removed":          sum(1 for c in changes if c.status == "removed"),
        "modified":         sum(1 for c in changes if c.status == "modified"),
        "total_size_delta": b.total_size - a.total_size,
    }
    return changes, summary


def format_text(changes: list[FileChange], summary: dict) -> str:
    lines = [
        f"size delta: {summary['total_size_delta']:+d} bytes",
        f"files: +{summary['added']} -{summary['removed']} ~{summary['modified']}",
    ]
    for c in changes[:20]:
        delta = c.size_b - c.size_a
        if c.status == "modified":
            lines.append(f"  ~ {c.path} {c.kind} {delta:+d}")
        elif c.status == "added":
            lines.append(f"  + {c.path} {c.kind} {c.size_b}B")
        elif c.status == "removed":
            lines.append(f"  - {c.path} {c.kind} {c.size_a}B")
    if len(changes) > 20:
        lines.append(f"  ... {len(changes) - 20} more")
    return "\n".join(lines)
