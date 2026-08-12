"""Record/replay MCP session tools."""
import time

from luna_mcp.config import data_dir as _data_dir
from luna_mcp.record.recorder import Recorder
from luna_mcp.record.replayer import Replayer

_DATA_DIR = _data_dir()
_recorder = Recorder(_DATA_DIR / "recordings")
_dispatch_fn = None  # overridable in tests


def _get_recorder() -> Recorder:
    return _recorder


def _get_dispatch():
    if _dispatch_fn is not None:
        return _dispatch_fn
    # Lazy import to avoid circular dependency at module load time
    from luna_mcp.tools.batch import dispatch as batch_dispatch
    return batch_dispatch


async def record_start(name: str) -> str:
    """Start recording tool calls to a named JSONL session."""
    rec = _get_recorder()
    if rec.active:
        return f"[INVALID: recording already active: {rec.session_id}]"
    try:
        path = rec.start(name)
    except (ValueError, RuntimeError) as e:
        return f"[INVALID: {e}]"
    return f"recording: {path}"


async def record_stop() -> str:
    """Stop active recording and save session file."""
    rec = _get_recorder()
    if not rec.active:
        return "[INVALID: no active recording]"
    path = rec.stop()
    return f"saved: {path}"


async def record_list() -> str:
    """List all recorded sessions."""
    rec = _get_recorder()
    paths = rec.list()
    if not paths:
        return "no recordings"
    lines = []
    for p in paths:
        st = p.stat()
        lines.append(f"{p.stem} | {st.st_size}B | {time.ctime(st.st_mtime)}")
    return "\n".join(lines)


async def replay(name: str, dry_run: bool = False) -> str:
    """Replay a recorded session against live Chrome and report divergences."""
    rec = _get_recorder()
    path = rec._base / f"{name}.jsonl"
    if not path.exists():
        return f"[INVALID: recording '{name}' not found]"
    replayer = Replayer(_get_dispatch())
    report = await replayer.replay(path, dry_run=dry_run)
    if report.diverged_at >= 0:
        tail = "\n".join(report.summary[-5:])
        return f"DIVERGED at step {report.diverged_at}/{report.total}: {report.divergence_reason}\n{tail}"
    tail = "\n".join(report.summary[-3:])
    return f"OK {report.ok_steps}/{report.total} steps\n{tail}"


async def record_diff(name: str, against: str) -> str:
    """Diff two recorded sessions step by step."""
    rec = _get_recorder()
    path_a = rec._base / f"{name}.jsonl"
    path_b = rec._base / f"{against}.jsonl"
    if not path_a.exists() or not path_b.exists():
        return "[INVALID: one or both recordings missing]"
    replayer = Replayer(_get_dispatch())
    return await replayer.diff(path_a, path_b)


def register_record_tools(mcp, *, exposed: set = frozenset()):
    from luna_mcp.tools import maybe_expose
    maybe_expose(mcp, record_start, exposed)
    maybe_expose(mcp, record_stop, exposed)
    maybe_expose(mcp, record_list, exposed)
    maybe_expose(mcp, replay, exposed)
    maybe_expose(mcp, record_diff, exposed)
    return {
        "record_start":  (record_start,  None),
        "record_stop":   (record_stop,   None),
        "record_list":   (record_list,   None),
        "replay":        (replay,        None),
        "record_diff":   (record_diff,   None),
    }
