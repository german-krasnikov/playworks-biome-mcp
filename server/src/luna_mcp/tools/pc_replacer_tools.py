"""5 MCP tools for PlayCanvas Module Replacement Recommender (F5)."""
from __future__ import annotations

from ..tools import maybe_expose


def _make_audit_pc_modules(scanner):
    async def audit_pc_modules() -> str:
        """Scan runtime usage of PlayCanvas modules. Returns text table."""
        if scanner is None:
            return "[DEGRADED:pc_replacer:not_initialized]"
        result = await scanner.scan()
        if not result:
            return "no modules scanned"
        lines = []
        for mid, info in result.items():
            lines.append(f"{mid:25} {info['usage']:8} {info['size_kb']:4}kb  {info['evidence'][:40]}")
        return "\n".join(lines)
    return audit_pc_modules


def _make_recommend_pc_replacements(scanner, recommender):
    async def recommend_pc_replacements(target_size_kb: int = 100) -> str:
        """Rank safe PlayCanvas module replacements to reach target_size_kb savings."""
        if scanner is None or recommender is None:
            return "[DEGRADED:pc_replacer:not_initialized]"
        scan = await scanner.scan()
        return await recommender.recommend(scan, target_size_kb)
    return recommend_pc_replacements


def _make_apply_pc_replacement(applier, catalog):
    async def apply_pc_replacement(module_id: str, dry_run: bool = True) -> str:
        """Stub a PlayCanvas module at runtime (monkey-patch). dry_run=True by default."""
        if applier is None:
            return "[DEGRADED:pc_replacer:not_initialized]"
        mod = catalog.get(module_id) if catalog else None
        if mod is None:
            return f"[INVALID: module '{module_id}' not in catalog]"
        if dry_run:
            return f"DRY_RUN: would stub {module_id} ({len(mod.exports)} exports, ~{mod.size_kb}kb)"
        return await applier.stub_module(module_id, mod.exports)
    return apply_pc_replacement


def _make_validate_pc_replacement(validator):
    async def validate_pc_replacement(baseline_name: str) -> str:
        """Compare current screenshot to saved baseline after module replacement."""
        if validator is None:
            return "[DEGRADED:pc_replacer:validator unavailable]"
        passed, summary = await validator.validate(baseline_name)
        return f"{'PASS' if passed else 'FAIL'}: {summary[:200]}"
    return validate_pc_replacement


def _make_revert_pc_replacement(applier, catalog):
    async def revert_pc_replacement(module_id: str) -> str:
        """Restore stubbed PlayCanvas module to original runtime state."""
        if applier is None:
            return "[DEGRADED:pc_replacer:not_initialized]"
        mod = catalog.get(module_id) if catalog else None
        if mod is None:
            return f"[INVALID: module '{module_id}' not in catalog]"
        return await applier.revert_module(module_id, mod.exports)
    return revert_pc_replacement


def register_pc_replacer_tools(
    mcp,
    *,
    catalog=None,
    scanner=None,
    recommender=None,
    applier=None,
    validator=None,
    exposed: set = frozenset(),
) -> dict:
    audit = _make_audit_pc_modules(scanner)
    recommend = _make_recommend_pc_replacements(scanner, recommender)
    apply_ = _make_apply_pc_replacement(applier, catalog)
    validate = _make_validate_pc_replacement(validator)
    revert = _make_revert_pc_replacement(applier, catalog)

    maybe_expose(mcp, audit, exposed)
    maybe_expose(mcp, recommend, exposed)
    maybe_expose(mcp, apply_, exposed, read_only=False)
    maybe_expose(mcp, validate, exposed)
    maybe_expose(mcp, revert, exposed, read_only=False)

    return {
        "audit_pc_modules":          (audit,    None),
        "recommend_pc_replacements": (recommend, None),
        "apply_pc_replacement":      (apply_,   None),
        "validate_pc_replacement":   (validate, None),
        "revert_pc_replacement":     (revert,   None),
    }
