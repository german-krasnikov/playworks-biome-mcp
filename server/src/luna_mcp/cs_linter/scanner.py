"""Scan C# files for forbidden expressions and required-API violations."""
from __future__ import annotations

import pathlib
import re

from .rules import RuleSet


def _cs_files(project_dir: pathlib.Path) -> list[pathlib.Path]:
    return list(project_dir.rglob("*.cs"))


def scan_forbidden(project_dir: pathlib.Path | str, rules: RuleSet) -> list[str]:
    """Return list of 'file:line: description' strings for forbidden hits."""
    root = pathlib.Path(project_dir)
    hits: list[str] = []
    for cs in _cs_files(root):
        try:
            lines = cs.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = cs.relative_to(root) if cs.is_relative_to(root) else cs
        for lineno, line in enumerate(lines, 1):
            hits.extend(_check_line(str(rel), lineno, line, rules))
    return hits


def _check_line(rel: str, lineno: int, line: str, rules: RuleSet) -> list[str]:
    hits: list[str] = []
    # member access: First.Second
    for ma in rules.member_access:
        pattern = rf'\b{re.escape(ma.first)}\.{re.escape(ma.second)}\b'
        if re.search(pattern, line):
            rule = f" [{ma.rule}]" if ma.rule else ""
            hits.append(f"{rel}:{lineno}: {ma.first}.{ma.second}{rule}")
    # assignment expressions (class-level identifier usage)
    for ae in rules.assignment_exprs:
        if re.search(rf'\b{re.escape(ae.name)}\b', line):
            rule = f" [{ae.rule}]" if ae.rule else ""
            hits.append(f"{rel}:{lineno}: {ae.name}{rule}")
    # forbidden function names
    for fn in rules.forbidden_functions:
        if re.search(rf'\bvoid\s+{re.escape(fn)}\b', line):
            hits.append(f"{rel}:{lineno}: forbidden function {fn}")
    # forbidden base types
    for bt in rules.forbidden_bases:
        if re.search(rf':\s*{re.escape(bt)}\b', line):
            hits.append(f"{rel}:{lineno}: forbidden base type {bt}")
    return hits


def scan_required_apis(project_dir: pathlib.Path | str, rules: RuleSet) -> list[str]:
    """Return list of required-API violation strings (min-count not met)."""
    root = pathlib.Path(project_dir)
    # Count occurrences across ALL files
    counts: dict[tuple[str, str], int] = {}
    for api in rules.required_apis:
        counts[(api.first, api.second)] = 0

    for cs in _cs_files(root):
        try:
            text = cs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for api in rules.required_apis:
            pattern = rf'\b{re.escape(api.first)}\b'
            if api.second:
                # check either First.Second or Second.First
                alt_pattern = rf'\b{re.escape(api.second)}\.{re.escape(api.first)}\b|\b{re.escape(api.first)}\.{re.escape(api.second)}\b'
                counts[(api.first, api.second)] += len(re.findall(alt_pattern, text))
            else:
                counts[(api.first, api.second)] += len(re.findall(pattern, text))

    violations: list[str] = []
    for api in rules.required_apis:
        found = counts[(api.first, api.second)]
        if found < api.min_count:
            label = f"{api.second}.{api.first}" if api.second else api.first
            rule = f" [{api.rule}]" if api.rule else ""
            violations.append(
                f"{label}{rule}: found {found}, required >= {api.min_count}"
            )
    return violations
