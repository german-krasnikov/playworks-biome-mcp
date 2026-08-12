"""LLM-assisted visual analysis tools for Luna playable ads.

Requires LUNA_VISUAL_LLM=1 and `claude` CLI in PATH.
"""
import os
import pathlib
import tempfile
import uuid
from typing import Callable, Optional

from ..sampling import SYS_UI
from ..tmp_cleanup import cleanup_old as _cleanup_old_tmp
from ..tmp_cleanup import track as _track_tmp
from . import maybe_expose

_DEGRADED = "[DEGRADED: visual LLM disabled — set LUNA_VISUAL_LLM=1 and install claude CLI]"

def _validate_screenshot_path(path: str) -> Optional[str]:
    """Returns error string or None if valid."""
    p = pathlib.Path(path).resolve()
    tmp = pathlib.Path(tempfile.gettempdir()).resolve()
    if not str(p).startswith(str(tmp)):
        return f"[INVALID: path must be under {tmp}]"
    if not p.exists():
        return f"[INVALID: file not found: {path}]"
    return None


_FOCUS_PROMPTS = {
    "ui": SYS_UI,
    "gameplay": "Describe the gameplay action visible. What is the player doing? 1-2 sentences.",
    "endcard": "Is there an end-card/install screen visible? Describe CTA, button text, position. Be brief.",
    "performance": "Any visual glitches, freezes, blank areas, or rendering artifacts? List them. None if clean.",
}


def register_llm_tools(mcp, sampling, get_bridge: Callable, *, exposed: set = frozenset()):
    """Register LLM visual tools. Returns {name: (fn, params)} for batch."""

    async def _take_screenshot() -> str:
        from ..config import SCREENSHOT_FORMAT, SCREENSHOT_MAX_WIDTH, SCREENSHOT_QUALITY
        bridge = get_bridge()
        data = await bridge.screenshot(format=SCREENSHOT_FORMAT, quality=SCREENSHOT_QUALITY,
                                       max_width=SCREENSHOT_MAX_WIDTH)
        _cleanup_old_tmp()
        ext = ".jpg" if SCREENSHOT_FORMAT == "jpeg" else ".png"
        path = os.path.join(tempfile.gettempdir(), f"luna_{uuid.uuid4().hex[:8]}{ext}")
        with open(path, "wb") as f:
            f.write(data)
        _track_tmp(pathlib.Path(path))
        return path

    async def analyze_screenshot(prompt: str = "Describe what is on screen") -> str:
        """Analyze the current Luna playable screenshot with Haiku. Returns a brief description."""
        if not sampling.enabled:
            return _DEGRADED
        path = await _take_screenshot()
        result = await sampling.describe_image(prompt, path)
        return result or "(no response from LLM)"
    maybe_expose(mcp, analyze_screenshot, exposed)

    async def verify_visual_state(expected: str) -> str:
        """Take a screenshot and verify expected visual state. Returns PASS or FAIL + reason."""
        if not sampling.enabled:
            return _DEGRADED
        path = await _take_screenshot()
        result = await sampling.verify_visual_state(expected, path)
        return result or "(no response from LLM)"
    maybe_expose(mcp, verify_visual_state, exposed)

    async def compare_screenshots(before_path: str, after_path: str, what_changed: str) -> str:
        """Compare two saved screenshots and describe what changed."""
        if not sampling.enabled:
            return _DEGRADED
        err = _validate_screenshot_path(before_path) or _validate_screenshot_path(after_path)
        if err:
            return err
        result = await sampling.verify_visual_diff(before_path, after_path, what_changed)
        return result or "(no response from LLM)"
    maybe_expose(mcp, compare_screenshots, exposed)

    async def describe_playable(focus: str = "ui") -> str:
        """Take screenshot and describe the Luna playable ad. focus: ui|gameplay|endcard|performance."""
        if not sampling.enabled:
            return _DEGRADED
        prompt = _FOCUS_PROMPTS.get(focus, _FOCUS_PROMPTS["ui"])
        path = await _take_screenshot()
        result = await sampling.describe_image(prompt, path)
        return result or "(no response from LLM)"
    maybe_expose(mcp, describe_playable, exposed)

    return {
        "analyze_screenshot": (analyze_screenshot, None),
        "verify_visual_state": (verify_visual_state, None),
        "compare_screenshots": (compare_screenshots, None),
        "describe_playable": (describe_playable, None),
    }
