"""Pure trace event summarizer — no CDP, no state."""
from __future__ import annotations

_FRAME_NAMES = {"DrawFrame", "BeginFrame", "Commit"}


def _frame_deltas_ms(chunks: list) -> list[float]:
    """Extract inter-frame deltas in ms from trace chunks."""
    # Collect timestamps of frame events (priority: DrawFrame > BeginFrame > Commit)
    frame_events: list[int] = []
    for ev in chunks:
        if ev.get("name") in _FRAME_NAMES:
            ts = ev.get("ts")
            if ts is not None:
                frame_events.append(ts)
    if len(frame_events) < 2:
        return []
    frame_events.sort()
    deltas = [(frame_events[i + 1] - frame_events[i]) / 1000.0 for i in range(len(frame_events) - 1)]
    return [d for d in deltas if d > 0]


def _long_tasks(chunks: list, min_dur_ms: float = 50.0) -> list[str]:
    """Return top-5 long tasks (cat contains 'toplevel', dur > 50ms)."""
    tasks = []
    for ev in chunks:
        cat = ev.get("cat", "")
        dur = ev.get("dur", 0)
        if "toplevel" in cat and dur / 1000.0 > min_dur_ms:
            tasks.append((dur, ev.get("name", "unknown")))
    tasks.sort(reverse=True)
    return [f"{name}  {dur/1000:.1f}ms" for dur, name in tasks[:5]]


def _task_based_fps(chunks: list) -> tuple[float, str]:
    """Fallback FPS estimate from task timestamps."""
    ts_list = sorted(ev["ts"] for ev in chunks if "ts" in ev)
    if len(ts_list) < 2:
        return 0.0, ""
    total_s = (ts_list[-1] - ts_list[0]) / 1_000_000.0
    if total_s <= 0:
        return 0.0, ""
    fps = len(ts_list) / total_s
    return fps, "(frame markers absent; task-based estimate)"


def summarize(chunks: list, overflow: bool = False) -> str:
    """Summarize trace chunks into frame timing stats + long tasks."""
    if not chunks:
        return "(no trace data)"
    deltas = _frame_deltas_ms(chunks)
    lines = []
    if deltas:
        avg = sum(deltas) / len(deltas)
        sorted_d = sorted(deltas)
        p95 = sorted_d[int(len(sorted_d) * 0.95)]
        fps = 1000.0 / avg if avg > 0 else 0
        jank = sum(1 for d in deltas if d > 33.0)
        lines.append(f"frames: {len(deltas) + 1}")
        lines.append(f"avg_frame: {avg:.1f}ms  fps: {fps:.1f}")
        lines.append(f"p95_frame: {p95:.1f}ms")
        lines.append(f"jank_frames (>33ms): {jank}")
    else:
        fps, note = _task_based_fps(chunks)
        if fps > 0:
            lines.append(f"fps: {fps:.1f}  {note}")
        else:
            lines.append("(frame markers absent; task-based estimate)")
    long = _long_tasks(chunks)
    if long:
        lines.append("long tasks:")
        lines.extend(f"  {t}" for t in long)
    if overflow:
        lines.append("[truncated]")
    return "\n".join(lines)
