"""Tests for EventBus and Subscription — RED phase."""
import asyncio

import pytest

from luna_mcp.cdp_bridge import EventBus


@pytest.fixture
def bus():
    return EventBus()


# 1. publish appends to buffer
def test_publish_appends_to_buf(bus):
    bus.publish("console", {"text": "hello", "level": "I"})
    snapped = bus.snapshot("console", count=10)
    assert len(snapped) == 1
    assert snapped[0]["text"] == "hello"


# 2. filter drops matching events before buf
def test_filter_drops_match_before_buf(bus):
    bus.set_filter("console", r"noise")
    bus.publish("console", {"text": "this is noise"})
    bus.publish("console", {"text": "important"})
    snapped = bus.snapshot("console", count=10)
    assert len(snapped) == 1
    assert snapped[0]["text"] == "important"


# 3. subscription matches first event
async def test_subscription_match_first_event(bus):
    import re
    sub = bus.subscribe({"console"}, re.compile("error"), max_events=1)
    bus.publish("console", {"text": "error occurred"})
    result = await asyncio.wait_for(sub.future, timeout=1.0)
    assert len(result) == 1
    assert "error" in result[0]["text"]


# 4. subscription collects N events
async def test_subscription_max_events_collects_n(bus):
    import re
    sub = bus.subscribe({"console"}, re.compile("error"), max_events=3)
    bus.publish("console", {"text": "error 1"})
    bus.publish("console", {"text": "error 2"})
    bus.publish("console", {"text": "error 3"})
    result = await asyncio.wait_for(sub.future, timeout=1.0)
    assert len(result) == 3


# 5. subscription does not match when pattern doesn't match
async def test_subscription_pattern_no_match(bus):
    import re
    sub = bus.subscribe({"console"}, re.compile("critical"), max_events=1)
    bus.publish("console", {"text": "info message"})
    bus.publish("console", {"text": "debug stuff"})
    assert not sub.future.done()
    assert len(sub.matches) == 0


# 6. snapshot since_seq filters correctly
def test_snapshot_since_seq_filters(bus):
    bus.publish("console", {"text": "msg0"})
    bus.publish("console", {"text": "msg1"})
    bus.publish("console", {"text": "msg2"})
    all_items = bus.snapshot("console", count=10)
    # seq starts at 0; get items after seq 0
    since_0 = bus.snapshot("console", count=10, since_seq=0)
    assert len(since_0) == 2  # seq 1 and 2


# 7. snapshot of unknown kind returns empty
def test_snapshot_kind_unknown_returns_empty(bus):
    result = bus.snapshot("unknown_kind", count=10)
    assert result == []


# 8. set_filter compiles regex
def test_set_filter_compiled(bus):
    bus.set_filter("console", r"\d+error")
    assert "console" in bus._filters
    bus.publish("console", {"text": "123error match"})
    snapped = bus.snapshot("console", count=10)
    assert len(snapped) == 0  # dropped by filter


# 9. set_filter clears when None/empty
def test_set_filter_clear(bus):
    bus.set_filter("console", r"noise")
    bus.set_filter("console", None)
    assert "console" not in bus._filters
    bus.publish("console", {"text": "noise passes now"})
    snapped = bus.snapshot("console", count=10)
    assert len(snapped) == 1


# 10. cancel_all cancels pending futures and clears subs
async def test_cancel_all_on_disconnect(bus):
    import re
    sub = bus.subscribe({"console"}, re.compile("x"), max_events=1)
    bus.cancel_all()
    assert sub.future.cancelled()
    assert bus._subs == []


# 11. publish unknown kind is silently ignored
def test_publish_unknown_kind_ignored(bus):
    bus.publish("bogus", {"text": "ignored"})
    assert bus.snapshot("console", count=10) == []


# 12. seq increments per event
def test_seq_increments(bus):
    bus.publish("console", {"text": "a"})
    bus.publish("network", {"text": "b"})
    c = bus.snapshot("console", count=10)
    n = bus.snapshot("network", count=10)
    assert c[0]["seq"] == 0
    assert n[0]["seq"] == 1


# 13. subscription wrong kind — no match
async def test_subscription_wrong_kind_no_match(bus):
    import re
    sub = bus.subscribe({"network"}, re.compile("error"), max_events=1)
    bus.publish("console", {"text": "error in console"})
    assert not sub.future.done()


# 14. M1: subscribe uses running loop (not deprecated get_event_loop)
async def test_subscribe_uses_running_loop(bus):
    """subscribe() must use asyncio.get_running_loop(), not get_event_loop()."""
    import re
    sub = bus.subscribe({"console"}, re.compile("x"), max_events=1)
    loop = asyncio.get_running_loop()
    # future must belong to the running loop
    assert sub.future.get_loop() is loop
