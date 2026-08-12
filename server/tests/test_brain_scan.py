"""Tests for BrainScanner (F20: Runtime Anomaly Detector)."""
import time

import pytest

from luna_mcp.watchdog.brain_scan import BrainScanner


class FakeSampling:
    def __init__(self, response="OK", enabled=True):
        self.enabled = enabled
        self._response = response
        self.calls = []

    async def plan(self, prompt, system):
        self.calls.append(prompt)
        return self._response


# ---------------------------------------------------------------------------
# Tier 1: threshold checks (no sampling)
# ---------------------------------------------------------------------------

def test_tier1_low_fps():
    bs = BrainScanner()
    findings = bs._check_thresholds("FPS: 15 draw calls: 50 heap: 50MB")
    assert any("LOW_FPS" in f for f in findings)


def test_tier1_high_drawcalls():
    bs = BrainScanner()
    findings = bs._check_thresholds("FPS: 60 draw calls: 250 heap: 100MB")
    assert any("HIGH_DRAWCALLS" in f for f in findings)


def test_tier1_high_memory():
    bs = BrainScanner()
    findings = bs._check_thresholds("FPS: 60 draw calls: 50 heap: 300MB")
    assert any("HIGH_MEMORY" in f for f in findings)


def test_tier1_no_issues():
    bs = BrainScanner()
    findings = bs._check_thresholds("FPS: 60 draw calls: 50 heap: 100MB")
    assert findings == []


def test_tier1_missing_values():
    bs = BrainScanner()
    # no parseable numbers — no crash, no false positives
    findings = bs._check_thresholds("no metrics here")
    assert findings == []


# ---------------------------------------------------------------------------
# Tier 2: Haiku disabled → Tier 1 only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_haiku_disabled_uses_tier1():
    bs = BrainScanner()
    sampling = FakeSampling(enabled=False)
    findings = await bs.analyze("no errors", "FPS: 15 draw calls: 50 heap: 50MB", sampling)
    assert any("LOW_FPS" in f for f in findings)
    assert sampling.calls == []  # Haiku never called


@pytest.mark.asyncio
async def test_no_sampling_object_uses_tier1():
    bs = BrainScanner()
    findings = await bs.analyze("no errors", "FPS: 15 draw calls: 50 heap: 50MB", None)
    assert any("LOW_FPS" in f for f in findings)


# ---------------------------------------------------------------------------
# Tier 2: Haiku enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_haiku_ok_returns_empty():
    bs = BrainScanner()
    sampling = FakeSampling(response="OK")
    findings = await bs.analyze("no errors", "FPS: 60 draw calls: 50 heap: 100MB", sampling)
    assert findings == []


@pytest.mark.asyncio
async def test_haiku_findings_parsed():
    bs = BrainScanner()
    sampling = FakeSampling(response="HIGH: memory leak detected\nWARN: particle loop")
    findings = await bs.analyze("some error", "FPS: 60", sampling)
    assert len(findings) == 2
    assert "HIGH: memory leak detected" in findings


# ---------------------------------------------------------------------------
# Dedup: same finding within 60s → not re-reported
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dedup_within_window():
    bs = BrainScanner()
    sampling = FakeSampling(response="WARN: shader fallback")

    # First call — scan debounce already bypassed by float("-inf") default
    findings1 = await bs.analyze("err", "FPS: 60", sampling)
    assert findings1 == ["WARN: shader fallback"]
    # Verify fingerprint recorded in _seen
    assert len(bs._seen) == 1

    # Second call: force scan debounce bypass, but _seen still has the fingerprint
    bs._last_scan = float("-inf")
    findings2 = await bs.analyze("err", "FPS: 60", sampling)
    # same fingerprint within debounce window → deduplicated
    assert findings2 == []


# ---------------------------------------------------------------------------
# Debounce: second call within 60s returns cached anomalies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_returns_cached():
    bs = BrainScanner()
    bs._debounce = 60.0
    bs._last_scan = time.monotonic() - 1.0  # scanned 1s ago
    bs._anomalies = ["CACHED: old finding"]
    sampling = FakeSampling(response="NEW: something new")

    findings = await bs.analyze("err", "FPS: 60", sampling)
    assert findings == ["CACHED: old finding"]
    assert sampling.calls == []  # Haiku not called again


# ---------------------------------------------------------------------------
# watchdog_report tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_watchdog_report_no_anomalies():
    from luna_mcp.tools.watchdog_tools import register_watchdog_tools

    class FakeMCP:
        def tool(self):
            def decorator(fn):
                return fn
            return decorator

    bs = BrainScanner()
    tools = register_watchdog_tools(FakeMCP(), get_brain_scanner=lambda: bs)
    report_fn = tools["watchdog_report"][0]
    result = await report_fn()
    assert result == "No anomalies detected"


@pytest.mark.asyncio
async def test_watchdog_report_with_anomalies():
    from luna_mcp.tools.watchdog_tools import register_watchdog_tools

    class FakeMCP:
        def tool(self):
            def decorator(fn):
                return fn
            return decorator

    bs = BrainScanner()
    bs._anomalies = ["HIGH: memory leak", "WARN: fps drop"]
    tools = register_watchdog_tools(FakeMCP(), get_brain_scanner=lambda: bs)
    report_fn = tools["watchdog_report"][0]
    result = await report_fn()
    assert "HIGH: memory leak" in result
    assert "WARN: fps drop" in result


@pytest.mark.asyncio
async def test_watchdog_report_no_scanner():
    from luna_mcp.tools.watchdog_tools import register_watchdog_tools

    class FakeMCP:
        def tool(self):
            def decorator(fn):
                return fn
            return decorator

    tools = register_watchdog_tools(FakeMCP(), get_brain_scanner=lambda: None)
    report_fn = tools["watchdog_report"][0]
    result = await report_fn()
    assert result == "No anomalies detected"
