"""Runtime monkey-patch: stub pc.X exports for testing."""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

_SAFE_ID = re.compile(r'^[a-z0-9_-]{1,64}$')
_SAFE_EXPORT = re.compile(r'^[a-zA-Z0-9_.]{1,80}$')


class StubApplier:
    """Replace pc.X with no-op stubs at runtime. Stores backup for revert."""

    def __init__(self, eval_fn: Callable[..., Awaitable[str]]):
        self._eval = eval_fn

    async def stub_module(self, module_id: str, exports: list[str]) -> str:
        if not _SAFE_ID.match(module_id):
            return f"[INVALID: module_id must match {_SAFE_ID.pattern}]"
        for ex in exports:
            if not _SAFE_EXPORT.match(ex):
                return f"[INVALID: export '{ex}' has unsafe chars]"

        js = ["window.__pc_replacer_backup = window.__pc_replacer_backup || {};"]
        for i, export in enumerate(exports):
            key = json.dumps(export)
            js.append(f"if (typeof {export} !== 'undefined' && !window.__pc_replacer_backup[{key}]) {{")
            js.append(f"  var _orig_{i} = {export};")
            js.append(f"  window.__pc_replacer_backup[{key}] = _orig_{i};")
            js.append(f"  {export} = function() {{ return Object.create(_orig_{i}.prototype || null); }};")
            js.append(f"  Object.assign({export}, _orig_{i});")
            js.append("}")
        js.append(f"'stubbed:'+{json.dumps(module_id)}")
        try:
            await self._eval("\n".join(js))
            return f"stubbed: {module_id} ({len(exports)} exports backed up)"
        except Exception as e:
            return f"[ERROR: {e}]"

    async def revert_module(self, module_id: str, exports: list[str]) -> str:
        if not _SAFE_ID.match(module_id):
            return f"[INVALID: module_id must match {_SAFE_ID.pattern}]"
        for ex in exports:
            if not _SAFE_EXPORT.match(ex):
                return f"[INVALID: export '{ex}' has unsafe chars]"

        js = ["if (window.__pc_replacer_backup) {"]
        for export in exports:
            key = json.dumps(export)
            js.append(f"  if (window.__pc_replacer_backup[{key}]) {{")
            js.append(f"    {export} = window.__pc_replacer_backup[{key}];")
            js.append(f"    delete window.__pc_replacer_backup[{key}];")
            js.append("  }")
        js.append("}")
        js.append(f"'reverted:{module_id}'")
        try:
            await self._eval("\n".join(js))
            return f"reverted: {module_id}"
        except Exception as e:
            return f"[ERROR: {e}]"
