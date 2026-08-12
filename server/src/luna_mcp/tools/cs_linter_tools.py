"""S5.2 C# Linter + Required-API Auditor — pure Python, no Chrome."""
from __future__ import annotations

import pathlib

from ..cs_linter.rules import load_rules
from ..cs_linter.scanner import scan_forbidden, scan_required_apis
from . import maybe_expose


def register_cs_linter_tools(mcp, *, exposed: set = frozenset()):
    async def lint_csharp(project_dir: str) -> str:
        """Scan C# files for forbidden expressions (NavMesh/OnGUI/OpenURL etc)."""
        root = pathlib.Path(project_dir)
        rules = load_rules(None, project_dir=root)
        prefix = "[DEGRADED:cs_linter:using seeded rules]\n" if rules.is_fallback else ""
        if not root.exists():
            return f"{prefix}error: project_dir not found: {project_dir}"
        hits = scan_forbidden(root, rules)
        if not hits:
            return f"{prefix}No forbidden expressions found."
        summary = f"{prefix}{len(hits)} hit(s) found:\n"
        return summary + "\n".join(hits[:50])

    async def audit_required_apis(project_dir: str) -> str:
        """Check required-API min-count violations (GameEnded, LogEvent etc)."""
        root = pathlib.Path(project_dir)
        rules = load_rules(None, project_dir=root)
        prefix = "[DEGRADED:cs_linter:using seeded rules]\n" if rules.is_fallback else ""
        if not root.exists():
            return f"{prefix}error: project_dir not found: {project_dir}"
        violations = scan_required_apis(root, rules)
        if not violations:
            return f"{prefix}All required APIs present."
        summary = f"{prefix}{len(violations)} required-API violation(s):\n"
        return summary + "\n".join(violations[:50])

    maybe_expose(mcp, lint_csharp, exposed, read_only=True)
    maybe_expose(mcp, audit_required_apis, exposed, read_only=True)
    return {
        "lint_csharp": (lint_csharp, None),
        "audit_required_apis": (audit_required_apis, None),
    }
