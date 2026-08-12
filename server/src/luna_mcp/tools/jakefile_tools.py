"""MCP tools for Jakefile Intelligence (F4)."""
from __future__ import annotations

import hashlib
import pathlib
from typing import Optional

from luna_mcp.build_intel.index import build_index
from luna_mcp.build_intel.locator import find_jakefile
from luna_mcp.build_intel.patch_dsl import PatchOp, apply_op, validate
from luna_mcp.build_intel.planner import JakefilePlanner, parse_dsl
from luna_mcp.build_intel.shadow_git import ShadowGit
from luna_mcp.build_intel.store import PatchStore
from luna_mcp.build_intel.templates import get_template, list_templates
from luna_mcp.config import data_dir as _data_dir
from luna_mcp.tools import maybe_expose

_DEFAULT_SHADOW = _data_dir() / "jakefile_patches"
_DEFAULT_DB = _data_dir() / "jakefile_patches.db"


def _project_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(str(path.parent).encode()).hexdigest()[:16]


def _make_analyze_jakefile():
    async def analyze_jakefile() -> str:
        """Return Jakefile.js index summary: version, tasks, anchor count."""
        p = find_jakefile()
        if p is None:
            return "[INVALID: Jakefile.js not found. Set LUNA_JAKEFILE_PATH env]"
        idx = build_index(p)
        return idx.to_summary()
    return analyze_jakefile


def _make_suggest_jakefile_patch(planner: Optional[JakefilePlanner]):
    async def suggest_jakefile_patch(intent: str) -> str:
        """Call Haiku planner for intent, return DSL preview with validation."""
        p = find_jakefile()
        if p is None:
            return "[INVALID: Jakefile.js not found]"
        if planner is None:
            return "[DEGRADED:planner:sampling disabled]"
        idx = build_index(p)
        dsl = await planner.plan(intent, idx)
        if not dsl:
            return "[PLANNER_UNAVAILABLE]"
        ops_kwargs = parse_dsl(dsl)
        if not ops_kwargs:
            return f"NO_VALID_OPS\n{dsl}"
        text = p.read_text(errors="replace")
        lines = []
        for kwargs in ops_kwargs:
            try:
                op = PatchOp(
                    id=kwargs["id"],
                    intent=kwargs.get("intent", intent),
                    search=kwargs["search"],
                    replace=kwargs["replace"],
                    expected_count=int(kwargs.get("count", 1)),
                    anchor_before=kwargs.get("anchor_before"),
                    anchor_after=kwargs.get("anchor_after"),
                )
            except (KeyError, TypeError) as e:
                lines.append(f"  [SKIP: bad kwargs {e}]")
                continue
            ok, reason = validate(op, text, idx)
            lines.append(f"  [{op.id}] {'OK' if ok else 'INVALID: ' + reason}")
        return "PLAN:\n" + dsl + "\n\nVALIDATION:\n" + "\n".join(lines)
    return suggest_jakefile_patch


def _make_apply_jakefile_patch(shadow_base: pathlib.Path, store: Optional[PatchStore] = None):
    _store = store or PatchStore(_DEFAULT_DB)

    async def apply_jakefile_patch(template_name: str, dry_run: bool = True) -> str:
        """Apply template patch to Jakefile.js. dry_run=True only previews."""
        p = find_jakefile()
        if p is None:
            return "[INVALID: Jakefile.js not found]"
        op = get_template(template_name)
        if op is None:
            return f"[INVALID: template '{template_name}' not found. Try: {', '.join(list_templates())}]"
        text = p.read_text(errors="replace")
        idx = build_index(p)
        ok, reason = validate(op, text, idx)
        if not ok:
            return f"[INVALID: {reason}]"
        new_text = apply_op(op, text)
        diff = f"size: {len(text)} → {len(new_text)} ({len(new_text) - len(text):+d} chars)"
        if dry_run:
            return f"DRY_RUN: would apply '{op.id}'\n{diff}"
        sg = ShadowGit(shadow_base, _project_hash(p))
        sg.init_if_needed()
        sg.stage_file(p, "Jakefile.js.before")
        p.write_text(new_text)
        sg.stage_file(p, "Jakefile.js.after")
        sha = sg.commit(f"biome patch {op.id}: {op.intent}")
        if sha is None:
            p.write_text(text)
            return "[ERROR: shadow commit failed; reverted file]"
        _store.record(op.id, op.intent, str(p), sha)
        return f"applied: {op.id} sha={sha}\n{diff}"
    return apply_jakefile_patch


def _make_revert_jakefile_patch(store: Optional[PatchStore] = None, shadow_base: pathlib.Path = _DEFAULT_SHADOW):
    _store = store or PatchStore(_DEFAULT_DB)

    async def revert_jakefile_patch(patch_id: str) -> str:
        """Revert an applied patch by ID using shadow git backup."""
        rec = _store.find(patch_id)
        if rec is None:
            return f"[INVALID: patch '{patch_id}' not in history]"
        if rec.get("status") == "reverted":
            return f"[INVALID: patch '{patch_id}' already reverted]"
        sg = ShadowGit(shadow_base, _project_hash(pathlib.Path(rec["jakefile_path"])))
        backup = sg.get_file("Jakefile.js.before")
        if backup is None:
            return "[ERROR: backup not found in shadow]"
        pathlib.Path(rec["jakefile_path"]).write_text(backup.read_text())
        revert_ok = sg.revert_commit(rec["shadow_commit_sha"])
        _store.update_status(patch_id, "reverted")
        if not revert_ok:
            return f"reverted: {patch_id} (warning: shadow git reset failed, file restored from backup)"
        return f"reverted: {patch_id}"
    return revert_jakefile_patch


def register_jakefile_tools(mcp, planner=None, shadow_base: pathlib.Path = _DEFAULT_SHADOW,
                             store=None, *, exposed: set = frozenset()):
    analyze_jakefile = _make_analyze_jakefile()
    suggest_jakefile_patch = _make_suggest_jakefile_patch(planner)
    apply_jakefile_patch = _make_apply_jakefile_patch(shadow_base, store)
    revert_jakefile_patch = _make_revert_jakefile_patch(store, shadow_base)

    maybe_expose(mcp, analyze_jakefile, exposed, name="analyze_jakefile")
    maybe_expose(mcp, suggest_jakefile_patch, exposed, name="suggest_jakefile_patch")
    maybe_expose(mcp, apply_jakefile_patch, exposed, name="apply_jakefile_patch", read_only=False)
    maybe_expose(mcp, revert_jakefile_patch, exposed, name="revert_jakefile_patch", read_only=False)

    return {
        "analyze_jakefile":       (analyze_jakefile,       None),
        "suggest_jakefile_patch": (suggest_jakefile_patch, None),
        "apply_jakefile_patch":   (apply_jakefile_patch,   None),
        "revert_jakefile_patch":  (revert_jakefile_patch,  None),
    }
