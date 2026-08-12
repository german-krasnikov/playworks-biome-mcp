"""MCP tools for Build Diff Analyzer (F3)."""
from __future__ import annotations

import pathlib
import re

from luna_mcp.build_diff.bisector import Bisector
from luna_mcp.build_diff.indexer import BuildIndex
from luna_mcp.tools import maybe_expose

_LABEL_RE = re.compile(r'^[a-z0-9_.-]{1,64}$')


def _make_index_build(store):
    async def index_build(path: str, label: str) -> str:
        """Scan a build folder and persist its manifest. label must be [a-z0-9_.-]{1,64}."""
        if not _LABEL_RE.match(label):
            return "[INVALID: label must match ^[a-z0-9_.-]{1,64}$]"
        p = pathlib.Path(path).expanduser().resolve()
        try:
            manifest = BuildIndex.scan(p, label)
        except ValueError as e:
            return f"[INVALID: {e}]"
        store.save(manifest)
        return f"indexed: {label} ({len(manifest.files)} files, {manifest.total_size}B)"
    return index_build


def _make_diff_builds(store, router):
    async def diff_builds(label_a: str, label_b: str, mode: str = "auto") -> str:
        """Diff two indexed builds. mode: file|semantic|visual|auto."""
        a = store.load(label_a)
        b = store.load(label_b)
        if a is None:
            return f"[INVALID: build '{label_a}' not indexed]"
        if b is None:
            return f"[INVALID: build '{label_b}' not indexed]"
        return await router.diff(a, b, mode)
    return diff_builds


def _make_list_builds(store):
    async def list_builds() -> str:
        """List all indexed builds."""
        items = store.list_all()
        if not items:
            return "no builds indexed"
        return "\n".join(f"{m.label} | {len(m.files)} files | {m.total_size}B" for m in items)
    return list_builds


def _make_bisect_change(store):
    async def bisect_change(good_label: str, bad_label: str, intermediates: str = "") -> str:
        """Binary search for regression culprit. intermediates = comma-separated labels."""
        inter = [s.strip() for s in intermediates.split(",") if s.strip()] if intermediates else []
        a = store.load(good_label)
        if a is None:
            return f"[INVALID: good_label '{good_label}' not indexed]"

        from luna_mcp.build_diff.file_diff import diff_manifests

        async def probe(label: str) -> bool:
            b = store.load(label)
            if not b:
                return False
            _, summary = diff_manifests(a, b)
            if a.total_size == 0:
                return True
            return abs(summary["total_size_delta"]) <= 0.05 * a.total_size

        bisector = Bisector(probe)
        culprit, probes = await bisector.find_culprit(good_label, bad_label, inter)
        return f"culprit: {culprit} ({probes} probes, criterion: size delta ≤5%)"
    return bisect_change


def register_build_diff_tools(mcp, store, router, *, exposed: set = frozenset()):
    """Register 4 build diff tools."""
    index_build = _make_index_build(store)
    diff_builds = _make_diff_builds(store, router)
    list_builds = _make_list_builds(store)
    bisect_change = _make_bisect_change(store)

    maybe_expose(mcp, index_build, exposed, name="index_build", read_only=False)
    maybe_expose(mcp, diff_builds, exposed, name="diff_builds")
    maybe_expose(mcp, list_builds, exposed, name="list_builds")
    maybe_expose(mcp, bisect_change, exposed, name="bisect_change")

    return {
        "index_build":    (index_build,    None),
        "diff_builds":    (diff_builds,    None),
        "list_builds":    (list_builds,    None),
        "bisect_change":  (bisect_change,  None),
    }
