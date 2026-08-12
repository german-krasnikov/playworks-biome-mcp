"""SchemaGuard: pre-flight validator — blocks typos before CDP eval."""
from __future__ import annotations

import logging
import os
from typing import Optional

from .schema_cache import SchemaCache

logger = logging.getLogger(__name__)

_GUARD: "SchemaGuard | None" = None  # wired by server.py

_VALIDATE = os.environ.get("LUNA_MCP_VALIDATE", "1") != "0"

_TRANSFORM_PROPS = frozenset(
    ["position", "rotation", "scale", "localPosition", "localScale"]
)

_REQUIRED: dict[str, list[str]] = {
    "set_property": ["path", "component_type", "prop", "value"],
    "set_transform": ["path", "prop", "x", "y", "z"],
    "get_component": ["path", "component_type"],
}

_PATH_CMDS = {"set_property", "set_transform", "get_component"}

LEV_BLOCK = 2


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la > lb:
        a, b, la, lb = b, a, lb, la
    row = list(range(la + 1))
    for j in range(1, lb + 1):
        prev = row[0]
        row[0] = j
        for i in range(1, la + 1):
            old = row[i]
            row[i] = min(row[i] + 1, row[i - 1] + 1,
                         prev + (0 if a[i - 1] == b[j - 1] else 1))
            prev = old
    return row[la]


def _best_match(bad: str, options) -> tuple[str, int]:
    if not options:
        return "", 999
    return min(((c, _levenshtein(bad, c)) for c in options), key=lambda x: x[1])


def _block(kind: str, bad: str, best: str, lev: int, where: str, known) -> str:
    known_str = ", ".join(list(known)[:5])
    return (
        f"[INVALID: {kind} '{bad}' on {where}]\n"
        f"[FIX: did you mean '{best}'? (lev={lev})]\n"
        f"[KNOWN: {known_str}]\n"
        f"[BYPASS: _no_validate=true]"
    )


class SchemaGuard:
    def __init__(self, cache: SchemaCache, typemap_resolver, runtime_call) -> None:
        self._cache = cache
        self._tm = typemap_resolver
        self._call = runtime_call

    async def validate(self, cmd: str, kw: dict, path_cache) -> Optional[str]:
        """Returns block string on bad input, None on pass. Fail-open on exception."""
        if not _VALIDATE:
            return None
        try:
            err = self._l1_shape(cmd, kw)
            if err:
                return err
            return await self._l2_semantic(cmd, kw)
        except Exception:
            logger.debug("SchemaGuard exception (fail-open)", exc_info=True)
            return None

    # ── L1: sync shape checks ─────────────────────────────────────────────────

    def _l1_shape(self, cmd: str, kw: dict) -> Optional[str]:
        # required keys
        for key in _REQUIRED.get(cmd, []):
            if key not in kw:
                return (
                    f"[INVALID: missing required arg '{key}' for {cmd}]\n"
                    f"[FIX: add {key}=...]\n"
                    f"[KNOWN: {', '.join(_REQUIRED[cmd])}]\n"
                    f"[BYPASS: _no_validate=true]"
                )
        # path prefix
        if cmd in _PATH_CMDS:
            path = kw.get("path", "")
            if path and not path.startswith("/"):
                return (
                    f"[INVALID: path '{path}' must start with '/']\n"
                    f"[FIX: use '/{path}']\n"
                    f"[KNOWN: paths always start with '/']\n"
                    f"[BYPASS: _no_validate=true]"
                )
        # set_transform prop whitelist
        if cmd == "set_transform":
            prop = kw.get("prop", "")
            if prop and prop not in _TRANSFORM_PROPS:
                best, lev = _best_match(prop, _TRANSFORM_PROPS)
                return _block("prop", prop, best, lev, "set_transform", _TRANSFORM_PROPS)
        return None

    # ── L2: async semantic checks ─────────────────────────────────────────────

    async def _l2_semantic(self, cmd: str, kw: dict) -> Optional[str]:
        if cmd not in ("set_property", "get_component"):
            return None

        comp = kw.get("component_type", "")
        if not comp:
            return None

        # typemap class check
        if self._tm.is_loaded():
            js = self._tm.get_js_class_name(comp)
            if js is None:
                known = list(self._tm.known_classes())
                best, lev = _best_match(comp, known)
                if lev <= LEV_BLOCK:
                    return _block("component_type", comp, best, lev, cmd, known)
                return None  # unknown but lev>2 — don't block

        if cmd != "set_property":
            return None

        # prop check against cached component props
        prop = kw.get("prop", "")
        if not prop:
            return None

        cached = self._cache.get(comp)
        if cached is None:
            return None  # no cached props — don't block

        if prop not in cached:
            best, lev = _best_match(prop, cached)
            if lev <= LEV_BLOCK:
                return _block("prop", prop, best, lev, f"{kw.get('path', '')}.{comp}", cached)
        return None
