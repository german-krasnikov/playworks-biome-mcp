"""C2(a) — window.traceResults.unusedModules ground-truth reader.

Tests mock the CDP eval; no Chrome required.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from luna_mcp.pc_replacer.catalog import ModuleCatalog, ModuleInfo
from luna_mcp.pc_replacer.scanner import UsageScanner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_catalog(*ids: str) -> ModuleCatalog:
    """Minimal catalog stub with given module IDs."""
    class _Cat:
        def all(self):
            return [ModuleInfo(id=i, exports=[], size_kb=50, category="other") for i in ids]
        def get(self, mid):
            return next((m for m in self.all() if m.id == mid), None)
    return _Cat()


def _make_scanner(catalog, eval_return: str) -> UsageScanner:
    eval_fn = AsyncMock(return_value=eval_return)
    return UsageScanner(catalog, eval_fn), eval_fn


# ---------------------------------------------------------------------------
# fetch_trace_unused — new helper on UsageScanner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_trace_unused_returns_list():
    """Should return a list of module IDs from window.traceResults."""
    cat = _make_catalog("particle", "physics3d")
    modules = ["particle", "physics3d"]
    eval_fn = AsyncMock(return_value=json.dumps(modules))
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.fetch_trace_unused()
    assert isinstance(result, list)
    assert "particle" in result


@pytest.mark.asyncio
async def test_fetch_trace_unused_empty_when_absent():
    """Returns [] when window.traceResults is absent (JS returns null/undefined)."""
    cat = _make_catalog("particle")
    eval_fn = AsyncMock(return_value="null")
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.fetch_trace_unused()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_trace_unused_empty_on_eval_error():
    """Returns [] when CDP eval raises (e.g. Chrome not connected)."""
    cat = _make_catalog("particle")
    eval_fn = AsyncMock(side_effect=RuntimeError("not connected"))
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.fetch_trace_unused()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_trace_unused_empty_list():
    """Returns [] when Luna reports no unused modules (empty array)."""
    cat = _make_catalog("particle")
    eval_fn = AsyncMock(return_value="[]")
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.fetch_trace_unused()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_trace_unused_filters_non_strings():
    """Skips non-string entries gracefully."""
    cat = _make_catalog("particle")
    eval_fn = AsyncMock(return_value=json.dumps(["particle", 42, None, "ui-2d"]))
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.fetch_trace_unused()
    assert result == ["particle", "ui-2d"]


# ---------------------------------------------------------------------------
# scan_with_trace — merges traceResults into scan result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_promotes_trace_unused_to_unused():
    """When traceResults says module is unused, scan should mark it 'unused'."""
    cat = _make_catalog("particle", "ui-2d")
    # First call returns trace list, subsequent calls return "false" for probes
    call_results = [json.dumps(["ui-2d"])] + ["false"] * 20
    eval_fn = AsyncMock(side_effect=call_results)
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.scan_with_trace()
    assert result["ui-2d"]["usage"] == "unused"
    assert "trace" in result["ui-2d"].get("source", "")


@pytest.mark.asyncio
async def test_scan_with_trace_falls_back_when_trace_absent():
    """When traceResults absent, behaves like regular scan."""
    cat = _make_catalog("particle")
    call_results = ["null"] + ["false"] * 20
    eval_fn = AsyncMock(side_effect=call_results)
    scanner = UsageScanner(cat, eval_fn)
    result = await scanner.scan_with_trace()
    assert "particle" in result
    # no 'trace' source since traceResults was absent
    assert result["particle"].get("source", "") != "trace"
