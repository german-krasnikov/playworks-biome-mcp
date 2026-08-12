"""Timeline tools: motion_summary (Tier 1), capture_timeline, analyze_animation,
compare_animation_states (Tier 2 with Haiku fallback)."""
import json
import pathlib
import tempfile
from typing import Callable, Optional

from .. import tmp_cleanup
from ..timeline import TimelineCapture, _LabelCache
from . import maybe_expose


def register_timeline_tools(
    mcp,
    get_bridge: Callable,
    get_sampling: Callable,
    get_cache: Optional[Callable] = None,
    *,
    exposed: set = frozenset(),
):
    _cache = get_cache() if get_cache else _LabelCache()

    def _make_capture():
        bridge = get_bridge()
        return TimelineCapture(
            screenshot_fn=lambda: bridge.screenshot(),
            tmp_dir=pathlib.Path(tempfile.gettempdir()),
            tmp_track_fn=tmp_cleanup.track,
        )

    async def motion_summary(path: str, duration_ms: int = 1000, samples: int = 8) -> str:
        """Tier 1 zero-LLM motion timeline of transform/animator/particles.
        Returns ASCII timeline with position, normalizedTime, particle count."""
        bridge = get_bridge()
        if bridge is None:
            return "[error: not connected]"
        expr = f"__luna_mcp.sampleMotionTimeline({json.dumps(path)}, {duration_ms}, {samples})"
        raw = await bridge.eval(expr)
        if not raw:
            return "[no data]"
        return f"TIMELINE: {path} ({duration_ms}ms, {samples} samples)\n{raw}"
    maybe_expose(mcp, motion_summary, exposed)

    async def capture_timeline(duration_ms: int = 1000, fps: int = 4) -> str:
        """Capture N screenshots over duration. Returns t=Xms /path lines. fps ≤ 8."""
        try:
            cap = _make_capture()
            frames = await cap.capture(duration_ms, fps)
        except ValueError as e:
            return f"[INVALID: {e}]"
        return "\n".join(f"t={f.t_ms}ms {f.path}" for f in frames)
    maybe_expose(mcp, capture_timeline, exposed)

    async def analyze_animation(
        target_path: str, focus: str = "motion", duration_ms: int = 1000, fps: int = 4
    ) -> str:
        """Tier 2: capture timeline frames + Haiku semantic verdict.
        Falls back to motion_summary when LUNA_VISUAL_LLM not enabled."""
        sampling = get_sampling()
        if not sampling or not sampling.enabled:
            return await motion_summary(target_path, duration_ms, fps)
        try:
            cap = _make_capture()
            frames = await cap.capture(duration_ms, fps)
        except ValueError as e:
            return f"[INVALID: {e}]"
        paths = [str(f.path) for f in frames]
        prompt = (
            f"Frames at {' '.join(f't={f.t_ms}ms' for f in frames)} "
            f"of '{target_path}' (focus={focus}). "
            "Describe motion: bouncing/static/glitchy/easing? ≤3 short bullets."
        )
        verdict = await sampling.describe_image_multi(prompt, paths)
        if verdict is None:
            return "PLANNER_UNAVAILABLE\nframes:\n" + "\n".join(paths)
        timeline = "\n".join(f"t={f.t_ms}ms {f.path.name}" for f in frames)
        return f"TIMELINE: {target_path} ({duration_ms}ms, {len(frames)} frames)\n{timeline}\nVERDICT: {verdict}"
    maybe_expose(mcp, analyze_animation, exposed)

    async def compare_animation_states(
        label_a: str, label_b: str, duration_ms: int = 1000, fps: int = 4
    ) -> str:
        """Capture state B and diff against cached state A.
        First call captures label_a. Mutate scene, call again to diff."""
        sampling = get_sampling()
        a_frames = _cache.get(label_a)
        if a_frames is None:
            try:
                cap = _make_capture()
                a_frames = await cap.capture(duration_ms, fps)
            except ValueError as e:
                return f"[INVALID: {e}]"
            _cache.set(label_a, a_frames)
            return (
                f"CAPTURED: {label_a} ({len(a_frames)} frames). "
                f"Now mutate scene and call again with label_b='{label_b}'."
            )
        try:
            cap = _make_capture()
            b_frames = await cap.capture(duration_ms, fps)
        except ValueError as e:
            return f"[INVALID: {e}]"
        _cache.set(label_b, b_frames)
        if not sampling or not sampling.enabled:
            return (
                f"DIFF: {len(a_frames)} vs {len(b_frames)} frames captured. "
                "Sampling disabled — use Tier 1 motion_summary."
            )
        paths = [str(f.path) for f in a_frames] + [str(f.path) for f in b_frames]
        prompt = (
            f"BEFORE/AFTER timeline. First {len(a_frames)} frames are state '{label_a}', "
            f"remaining {len(b_frames)} are '{label_b}'. "
            "List visual differences in motion/transitions."
        )
        verdict = await sampling.describe_image_multi(prompt, paths)
        return f"DIFF {label_a} → {label_b}\n{verdict or '[no verdict — sampling failed]'}"
    maybe_expose(mcp, compare_animation_states, exposed)

    return {
        "motion_summary": (motion_summary, None),
        "capture_timeline": (capture_timeline, None),
        "analyze_animation": (analyze_animation, None),
        "compare_animation_states": (compare_animation_states, None),
    }
