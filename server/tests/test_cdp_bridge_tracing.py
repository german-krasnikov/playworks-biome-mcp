"""Tests for Tracing event handling added to CDPBridge."""
import asyncio

import pytest


def make_bridge():
    from luna_mcp.cdp_bridge import CDPBridge
    b = CDPBridge(port=9999)
    return b


def push_event(bridge, method, params):
    """Simulate the bridge's _read_loop receiving a CDP event message."""
    data = {"method": method, "params": params}
    # Directly call the internal parse branch (no WebSocket needed)
    bridge._handle_event(data)


# --- start/take ---

def test_start_trace_clears_chunks():
    bridge = make_bridge()
    bridge._trace_chunks = [1, 2, 3]
    bridge._trace_overflow = True
    bridge.start_trace_collection()
    assert bridge._trace_chunks == []
    assert bridge._trace_overflow is False
    assert bridge._tracing_active is True


def test_take_trace_chunks_clears():
    bridge = make_bridge()
    bridge._trace_chunks = [{"ph": "X"}]
    chunks = bridge.take_trace_chunks()
    assert len(chunks) == 1
    assert bridge._trace_chunks == []


# --- event handling ---

def test_dataCollected_appends_to_chunks():
    bridge = make_bridge()
    bridge.start_trace_collection()
    data = {"method": "Tracing.dataCollected", "params": {"value": [{"ph": "B"}, {"ph": "E"}]}}
    bridge._handle_event(data)
    assert len(bridge._trace_chunks) == 2


def test_dataCollected_not_put_in_events_queue():
    bridge = make_bridge()
    bridge.start_trace_collection()
    data = {"method": "Tracing.dataCollected", "params": {"value": [{"ph": "B"}]}}
    bridge._handle_event(data)
    assert bridge._events.empty()


def test_dataCollected_ignored_when_not_active():
    bridge = make_bridge()
    # _tracing_active defaults False
    data = {"method": "Tracing.dataCollected", "params": {"value": [{"ph": "X"}]}}
    bridge._handle_event(data)
    assert bridge._trace_chunks == []


def test_tracingComplete_sets_done_event():
    bridge = make_bridge()
    bridge.start_trace_collection()
    data = {"method": "Tracing.tracingComplete", "params": {}}
    bridge._handle_event(data)
    assert bridge._tracing_active is False
    assert bridge._trace_done.is_set()


# --- overflow cap ---

def test_overflow_cap_at_200k():
    bridge = make_bridge()
    bridge.start_trace_collection()
    # Fill up to just over 200_000
    big_chunk = [{"ph": "X"}] * 100
    for _ in range(2001):  # 2001 * 100 = 200100 > 200000
        data = {"method": "Tracing.dataCollected", "params": {"value": big_chunk}}
        bridge._handle_event(data)
    assert bridge._trace_overflow is True
    # After overflow, further chunks are NOT appended
    before = len(bridge._trace_chunks)
    bridge._handle_event({"method": "Tracing.dataCollected", "params": {"value": [{"ph": "Y"}]}})
    assert len(bridge._trace_chunks) == before


# --- wait_trace_complete ---

@pytest.mark.asyncio
async def test_wait_trace_complete_resolves():
    bridge = make_bridge()
    bridge.start_trace_collection()

    async def signal():
        await asyncio.sleep(0.01)
        bridge._handle_event({"method": "Tracing.tracingComplete", "params": {}})

    asyncio.create_task(signal())
    await bridge.wait_trace_complete(timeout=2.0)
    assert bridge._trace_done.is_set()


@pytest.mark.asyncio
async def test_wait_trace_complete_timeout():
    bridge = make_bridge()
    bridge.start_trace_collection()
    with pytest.raises(asyncio.TimeoutError):
        await bridge.wait_trace_complete(timeout=0.05)
