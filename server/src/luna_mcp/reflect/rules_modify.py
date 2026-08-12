"""Reflection rules for set_property and set_transform mutations."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from . import Mismatch, _values_close, register_rule

# Module-level call_fn — replaced by server.py after init; patchable in tests.
_call_fn = None

# Physics-driven props that change every frame — reflecting them is noise.
_REFLECT_SKIP_PROPS = frozenset({"velocity", "angularVelocity", "angularDrag"})


def _parse_vec(v) -> Optional[tuple]:
    """Extract (x,y,z) from dict or list."""
    if isinstance(v, dict):
        try:
            return float(v.get("x", 0)), float(v.get("y", 0)), float(v.get("z", 0))
        except (TypeError, ValueError):
            return None
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        try:
            return float(v[0]), float(v[1]), float(v[2])
        except (TypeError, ValueError):
            return None
    return None


@register_rule("set_property")
async def _rule_set_property(args, kw, response, _ignored_call) -> Optional[Mismatch]:
    if _call_fn is None:
        return None
    path = kw.get("path") or (args[0] if args else None)
    prop = kw.get("prop") or (args[2] if len(args) > 2 else None)
    value = kw.get("value") or (args[3] if len(args) > 3 else None)
    if not path or not prop:
        return None
    if prop in _REFLECT_SKIP_PROPS:
        return None  # physics-driven — skip reflect

    await asyncio.sleep(0.016)
    try:
        raw = await _call_fn("readBack", path, prop)
        snap = json.loads(raw)
    except Exception:
        return None

    if not snap.get("ok"):
        return None
    if not snap.get("exists"):
        return Mismatch(f"{path} not found after write")

    actual = snap["value"]
    if value is not None and not _values_close(value, actual):
        return Mismatch(f"{prop}: expected {value}, got {actual}")
    return None


@register_rule("set_transform")
async def _rule_set_transform(args, kw, response, _ignored_call) -> Optional[Mismatch]:
    if _call_fn is None:
        return None
    path = kw.get("path") or (args[0] if args else None)
    prop = kw.get("prop") or (args[1] if len(args) > 1 else None)
    ex = kw.get("x") if kw.get("x") is not None else (args[2] if len(args) > 2 else None)
    ey = kw.get("y") if kw.get("y") is not None else (args[3] if len(args) > 3 else None)
    ez = kw.get("z") if kw.get("z") is not None else (args[4] if len(args) > 4 else None)
    if not path or not prop:
        return None

    await asyncio.sleep(0.033)
    try:
        raw = await _call_fn("readBack", path, f"transform.{prop}")
        snap = json.loads(raw)
    except Exception:
        return None

    if not snap.get("ok"):
        return None
    if not snap.get("exists"):
        return Mismatch(f"{path} read failed after set_transform")

    actual = snap["value"]
    vec = _parse_vec(actual)
    if vec is None or ex is None:
        return None

    expected_vec = (float(ex), float(ey), float(ez))
    for exp_c, act_c in zip(expected_vec, vec):
        if not _values_close(exp_c, act_c):
            return Mismatch(f"{prop}: expected {expected_vec}, got {vec}")
    return None
