"""Reflection rule for eval_js: verify iframe still responsive after assignment."""
from __future__ import annotations

import re
from typing import Optional

from . import Mismatch, register_rule

# Patchable in tests
_ping_fn = None

# bare = (assignment): not preceded by =, !, <, > and not followed by =
_ASSIGN_RE = re.compile(r'(?<![=!<>])=(?!=)')
# compound assignments: +=, -=, *=, /=, %=, ??=, ||=, &&=, **=, <<=, >>=, >>>=
_COMPOUND_RE = re.compile(r'[+\-*/%]=|[?|&]{2}=|<<=|>>>=|>>=|\*\*=')


@register_rule("eval_js")
async def _rule_eval_js(args, kw, response, _ignored_call) -> Optional[Mismatch]:
    expr = kw.get("expression") or (args[0] if args else "")
    has_assign = bool(_ASSIGN_RE.search(expr) or _COMPOUND_RE.search(expr))
    if not has_assign:
        return None

    if _ping_fn is None:
        return None

    try:
        pong = await _ping_fn()
    except Exception:
        return None

    if not pong:
        return Mismatch("iframe unresponsive after eval_js — helpers may need re-injection")
    return None
