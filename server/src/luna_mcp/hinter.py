"""ToolHinter — behavioral anti-pattern detection via N-gram ring buffer."""
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from .hinter_rules import _RULES_BASE


@dataclass
class _Call:
    name: str
    key: str
    ts: float
    out_tag: str  # "BUDGET"|"INVALID"|"REFLECT"|"DEGRADED"|"OK"


class ToolHinter:
    """Watches last 12 calls, fires hints on anti-patterns. ≤80 char hints."""

    def __init__(self):
        self.history: deque[_Call] = deque(maxlen=12)
        self._suppress: dict[str, int] = {}       # rule_id -> calls_until_unmute
        self._pending: dict[str, int] = {}         # rule_id -> calls_left_for_adoption_check
        self._ignored_count: dict[str, int] = {}   # rule_id -> consecutive ignores

    def observe(self, name: str, kw: dict, out: str) -> Optional[str]:
        """Record call, return hint string (≤80 chars) or None."""
        self._check_adoption(name)
        key = self._canonical_key(name, kw)
        out_tag = self._extract_tag(out)
        self.history.append(_Call(name=name, key=key, ts=time.time(), out_tag=out_tag))
        for rid in list(self._suppress):
            self._suppress[rid] -= 1
            if self._suppress[rid] <= 0:
                del self._suppress[rid]
        for rid, rule_fn in _RULES:
            if rid in self._suppress:
                continue
            hint = rule_fn(self.history, name, kw, out_tag)
            if hint:
                self._pending[rid] = 3
                self._ignored_count.setdefault(rid, 0)
                return f"[HINT:{rid}: {hint}]"
        return None

    def _canonical_key(self, name: str, kw: dict) -> str:
        if name == "eval_js":
            return f"eval_js:{(kw.get('expression') or '')[:60]}"
        if name in ("set_property", "set_transform", "diagnose_object", "get_object_detail"):
            return f"{name}:{kw.get('path', '')}"
        return name

    def _extract_tag(self, out: str) -> str:
        if not isinstance(out, str):
            return "OK"
        if "[INVALID:" in out:
            return "INVALID"
        if "[skipped " in out or "[budget hint:" in out:
            return "BUDGET"
        if "[REFLECT:" in out:
            return "REFLECT"
        if "[DEGRADED:" in out:
            return "DEGRADED"
        return "OK"

    def _check_adoption(self, current_name: str) -> None:
        for rid in list(self._pending):
            self._pending[rid] -= 1
            if self.history and current_name != self.history[-1].name:
                self._ignored_count[rid] = 0
            elif self._pending[rid] <= 0:
                self._ignored_count[rid] = self._ignored_count.get(rid, 0) + 1
                if self._ignored_count[rid] >= 2:
                    self._suppress[rid] = 8
                    self._ignored_count[rid] = 0
            if self._pending[rid] <= 0:
                del self._pending[rid]


_RULES = list(_RULES_BASE)
