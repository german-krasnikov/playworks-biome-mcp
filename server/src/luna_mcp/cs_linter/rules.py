"""Load Roslyn lint rules from roslyn-data.json or seeded fallback."""
from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, field
from typing import Optional

# ── data models ──────────────────────────────────────────────────────────────

@dataclass
class MemberAccess:
    first: str
    second: str
    rule: str = ""
    is_luna: bool = False


@dataclass
class RequiredApi:
    first: str
    second: str
    min_count: int = 1
    is_error: bool = True
    rule: str = ""


@dataclass
class AssignmentExpr:
    name: str
    rule: str = ""


@dataclass
class RuleSet:
    member_access: list[MemberAccess] = field(default_factory=list)
    assignment_exprs: list[AssignmentExpr] = field(default_factory=list)
    required_apis: list[RequiredApi] = field(default_factory=list)
    forbidden_functions: list[str] = field(default_factory=list)
    forbidden_bases: list[str] = field(default_factory=list)
    min_custom_events: int = 3
    is_fallback: bool = False


# ── seeded fallback ──────────────────────────────────────────────────────────

_SEED: RuleSet = RuleSet(
    member_access=[
        MemberAccess("Application", "OpenURL", rule="LP3014"),
        MemberAccess("JsonUtility", "ToJson", rule=""),
        MemberAccess("GameObject", "FindGameObjectWithTag", rule="LP-perf: avoid Find at runtime"),
        MemberAccess("AnimationCurve", "AddKey", rule="LP-perf: avoid AddKey at runtime"),
    ],
    assignment_exprs=[
        AssignmentExpr("NavMesh", rule="IsFullyUnsupported"),
    ],
    required_apis=[
        RequiredApi("GameEnded", "LifeCycle", min_count=1, is_error=True, rule="LP3015"),
        RequiredApi("LogEvent", "Analytics", min_count=3, is_error=True, rule=""),
        RequiredApi("InstallFullGame", "Playable", min_count=1, is_error=True, rule=""),
    ],
    forbidden_functions=["OnGUI"],
    forbidden_bases=["Editor"],
    min_custom_events=3,
    is_fallback=True,
)


# ── loader ───────────────────────────────────────────────────────────────────

def _find_roslyn_json(project_dir: Optional[pathlib.Path] = None) -> Optional[pathlib.Path]:
    plugin = os.environ.get("LUNA_PLUGIN_PATH", "")
    if plugin:
        p = pathlib.Path(plugin) / "tools" / "diagnostics" / "roslyn-data.json"
        if p.exists():
            return p
    # glob from project_dir (if given), then cwd
    _pkg_root = "Common" + "Packages"
    _glob_pat = f"{_pkg_root}/Playworks/*/tools/diagnostics/roslyn-data.json"
    search_roots = [project_dir] if project_dir else []
    search_roots.append(pathlib.Path("."))
    for base in search_roots:
        for candidate in pathlib.Path(base).glob(_glob_pat):
            return candidate
    return None


def _parse(data: dict) -> RuleSet:
    rs = RuleSet()
    for e in data.get("MemberAccessExpressionsToCheck", []):
        rs.member_access.append(MemberAccess(
            first=e.get("FirstExpression", ""),
            second=e.get("SecondExpression", ""),
            rule=e.get("Rule", ""),
            is_luna=e.get("IsLunaAPI", False),
        ))
    for e in data.get("AssignmentExpressionsToCheck", []):
        rs.assignment_exprs.append(AssignmentExpr(
            name=e.get("FirstExpression", e.get("Name", "")),
            rule=e.get("Rule", ""),
        ))
    for e in data.get("LunaAPIsToCheck", []):
        rs.required_apis.append(RequiredApi(
            first=e.get("FirstExpression", ""),
            second=e.get("SecondExpression", ""),
            min_count=e.get("minimumRequiredPresentInCode", 1),
            is_error=e.get("isError", True),
            rule=e.get("Rule", ""),
        ))
    rs.forbidden_functions = list(data.get("FunctionNamesToCheck", []))
    rs.forbidden_bases = list(data.get("BaseTypesToCheck", []))
    rs.min_custom_events = data.get("minCustomEventsUsage", 3)
    return rs


def load_rules(path: Optional[pathlib.Path], project_dir: Optional[pathlib.Path] = None) -> RuleSet:
    """Load rules from path → env/glob discovery → seeded fallback."""
    target = path or _find_roslyn_json(project_dir)
    if target is None:
        return _SEED
    try:
        data = json.loads(pathlib.Path(target).read_text(encoding="utf-8"))
        return _parse(data)
    except Exception:
        return _SEED
