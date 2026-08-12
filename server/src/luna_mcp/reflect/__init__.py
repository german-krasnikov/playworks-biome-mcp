"""Asymmetric Reflection: post-mutation verification middleware."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

__all__ = ["Mismatch", "register_rule", "_RULES", "with_reflect", "_values_close"]


@dataclass(frozen=True)
class Mismatch:
    msg: str


ReflectFn = Callable[[dict, dict, str, Callable], Awaitable[Optional[Mismatch]]]
_RULES: dict[str, ReflectFn] = {}


def register_rule(cmd: str) -> Callable[[ReflectFn], ReflectFn]:
    def deco(fn: ReflectFn) -> ReflectFn:
        _RULES[cmd] = fn
        return fn
    return deco


def _values_close(expected, actual, rel_tol: float = 1e-4, abs_tol: float = 1e-5) -> bool:
    """Numeric close (scalar/Vector3 dict), string equality, bool match."""
    # dict / Vector3 component-wise
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k in expected:
            if k not in actual:
                return False
            if not _values_close(expected[k], actual[k], rel_tol, abs_tol):
                return False
        return True

    # bool exact
    e_str = str(expected).lower().strip()
    a_str = str(actual).lower().strip()
    if e_str in ("true", "false") or a_str in ("true", "false"):
        return e_str == a_str

    # numeric
    try:
        return math.isclose(float(expected), float(actual), rel_tol=rel_tol, abs_tol=abs_tol)
    except (ValueError, TypeError):
        pass

    return str(expected) == str(actual)


_ERROR_PREFIXES = ("Error", "Failed", "[INVALID:", "[BATCH ABORTED")


def _is_error(result: str) -> bool:
    return any(result[:60].startswith(p) for p in _ERROR_PREFIXES)


def with_reflect(cmd: str, fn) -> Callable:
    """Wrap fn: after execution, run registered rule and append [REFLECT:...] on mismatch."""

    async def wrapped(*args, **kw):
        if kw.pop("_no_reflect", False):
            return await fn(*args, **kw)
        if os.environ.get("LUNA_REFLECT", "1") == "0":
            return await fn(*args, **kw)

        result = await fn(*args, **kw)

        if isinstance(result, str) and _is_error(result):
            return result

        rule = _RULES.get(cmd)
        if rule is None:
            return result

        try:
            mismatch = await rule(args, kw, result, None)
            if mismatch:
                return f"{result}\n[REFLECT: {mismatch.msg}]"
        except Exception:
            pass  # fail-open

        return result

    return wrapped


# Auto-register rules by importing sub-modules
from . import rules_modify, rules_runtime  # noqa: E402,F401
