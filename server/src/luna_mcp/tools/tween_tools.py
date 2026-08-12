"""S3.2 DOTween inventory and control tools."""
import asyncio
import re

from . import maybe_expose

_VALID_ACTIONS = {"pause", "play", "kill", "complete"}


def _parse_tween_lines(raw: str) -> list[dict]:
    """Parse tween list output into list of {idx, pos, loops, playing} dicts."""
    entries = []
    for line in raw.strip().splitlines():
        m_idx = re.match(r"^(\d+)\s*\|", line)
        if not m_idx:
            continue
        idx = int(m_idx.group(1))
        pos = None
        loops = None
        playing = None
        m = re.search(r"pos=([\d.]+)", line)
        if m:
            pos = float(m.group(1))
        m = re.search(r"loops=(-?\d+)", line)
        if m:
            loops = int(m.group(1))
        m = re.search(r"playing=(True|False)", line)
        if m:
            playing = m.group(1) == "True"
        entries.append({"idx": idx, "pos": pos, "loops": loops, "playing": playing, "line": line})
    return entries


def register_tween_tools(mcp, call_fn, *, exposed: set = frozenset()):
    """Register DOTween tools. Returns {name: (fn, params)} for batch."""

    async def tween_inventory() -> str:
        """List all active DOTween tweens. Returns 'DOTween not present' if unavailable."""
        return await call_fn("tweenList")
    maybe_expose(mcp, tween_inventory, exposed, read_only=True)

    async def tween_health(interval_ms: int = 250) -> str:
        """Two-sample DOTween health check. Flags STUCK (pos unchanged) and INFINITE tweens."""
        snap1_raw = await call_fn("tweenList")
        if interval_ms > 0:
            await asyncio.sleep(interval_ms / 1000)
        snap2_raw = await call_fn("tweenList")
        snap1 = _parse_tween_lines(str(snap1_raw or ""))
        snap2 = _parse_tween_lines(str(snap2_raw or ""))
        pos2 = {e["idx"]: e for e in snap2}
        issues = []
        for e in snap1:
            idx = e["idx"]
            if e["loops"] == -1 and e["playing"]:
                issues.append(f"INFINITE idx={idx}")
            if idx in pos2 and e["pos"] is not None and pos2[idx]["pos"] == e["pos"] and e["playing"]:
                issues.append(f"STUCK idx={idx}")
        if not issues:
            return "OK"
        return "\n".join(issues)
    maybe_expose(mcp, tween_health, exposed, read_only=True)

    async def tween_control(action: str) -> str:
        """Control all tweens: pause|play|kill|complete."""
        if action not in _VALID_ACTIONS:
            return "[INVALID: action must be pause|play|kill|complete]"
        return await call_fn("tweenControl", action)
    maybe_expose(mcp, tween_control, exposed, read_only=False)

    return {
        "tween_inventory": (tween_inventory, None),
        "tween_health": (tween_health, None),
        "tween_control": (tween_control, None),
    }
