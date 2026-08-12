"""Runtime usage detection via CDP eval."""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from .catalog import ModuleCatalog, ModuleInfo

_TRACE_JS = (
    "JSON.stringify("
    "window.traceResults && window.traceResults.unusedModules "
    "? window.traceResults.unusedModules : null"
    ")"
)


class UsageScanner:
    def __init__(self, catalog: ModuleCatalog, eval_fn: Callable[..., Awaitable[str]]):
        self._catalog = catalog
        self._eval = eval_fn

    async def fetch_trace_unused(self) -> list[str]:
        """Read Luna's live dead-module list from window.traceResults.unusedModules.

        Returns [] when absent or on any error (graceful degradation).
        """
        try:
            raw = await self._eval(_TRACE_JS)
            parsed = json.loads(str(raw))
            if not parsed:
                return []
            return [s for s in parsed if isinstance(s, str)]
        except Exception:
            return []

    async def scan_with_trace(self) -> dict[str, dict]:
        """Scan all modules, then override 'unused' entries from traceResults."""
        trace_unused = await self.fetch_trace_unused()
        result = await self.scan()
        for mod_id in trace_unused:
            if mod_id in result:
                result[mod_id]["usage"] = "unused"
                result[mod_id]["source"] = "trace"
        return result

    async def scan(self) -> dict[str, dict]:
        """Returns {module_id: {usage, evidence, size_kb}}."""
        result = {}
        for mod in self._catalog.all():
            result[mod.id] = await self._scan_module(mod)
        return result

    async def _scan_module(self, mod: ModuleInfo) -> dict:
        evidence = []
        any_defined = False
        any_used = False

        for export in mod.exports:
            try:
                raw = await self._eval(f"typeof {export} !== 'undefined'")
                exists = "true" in str(raw).lower()
            except Exception:
                exists = False

            if exists:
                any_defined = True
                evidence.append(f"{export}=defined")

            if exists and "Component" in export:
                try:
                    name = export.split(".")[-1].replace("Component", "").lower()
                    raw = await self._eval(
                        f"(function(){{var s=window.app&&window.app.app&&window.app.app.systems"
                        f"&&window.app.app.systems['{name}'];"
                        f"return s&&s.store?Object.keys(s.store).length:-1}})()"
                    )
                    m = re.search(r"-?\d+", str(raw))
                    cnt = int(m.group()) if m else -1
                    if cnt > 0:
                        any_used = True
                        evidence.append(f"{name}.count={cnt}")
                except Exception:
                    pass

        if not any_defined:
            usage = "unused"
        elif any_used:
            usage = "used"
        else:
            usage = "partial"

        return {
            "usage": usage,
            "evidence": "; ".join(evidence) or "no probes",
            "size_kb": mod.size_kb,
        }
