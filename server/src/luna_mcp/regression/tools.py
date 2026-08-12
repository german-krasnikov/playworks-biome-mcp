"""4 MCP regression tools: save/check/list/invalidate baselines."""
import pathlib
import re
import tempfile
import uuid

from . import determinism as _determinism_mod
from .differ import diff_pct
from .store import BaselineStore, get_build_hash

_NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _validate_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


class RegressionTools:
    def __init__(self, bridge, store: BaselineStore, sampling):
        self._bridge = bridge
        self._store = store
        self._sampling = sampling

    async def visual_baseline_save(self, name: str, mask_zones: str = "",
                                   semantic_hint: str = "",
                                   pixel_threshold: float = 1.0) -> str:
        """Capture screenshot and save as named baseline."""
        if not _validate_name(name):
            return "[INVALID: name must match ^[a-z0-9_-]{1,64}$]"
        bh = await get_build_hash(self._bridge)
        png = await self._bridge.screenshot()
        await self._store.save(bh, name, png, mask_zones=mask_zones,
                               semantic_hint=semantic_hint,
                               pixel_threshold=pixel_threshold)
        return f"saved baseline '{name}' for build {bh}"

    async def visual_baseline_check(self, name: str, semantic_hint: str = "") -> str:
        """Compare current screenshot to saved baseline."""
        if not _validate_name(name):
            return "[INVALID: name must match ^[a-z0-9_-]{1,64}$]"
        bh = await get_build_hash(self._bridge)
        loaded = self._store.load(bh, name)
        if loaded is None:
            return f"[INVALID: baseline '{name}' not found for build {bh}; use visual_baseline_save first]"
        baseline_path, meta = loaded
        await _determinism_mod.prepare_deterministic(self._bridge)
        current = await self._bridge.screenshot()
        pct, err = diff_pct(baseline_path, current, mask_zones=meta.get("mask_zones", ""))
        if err:
            return f"FAIL {err}"
        threshold = meta.get("pixel_threshold", 1.0)
        if pct < threshold:
            return f"PASS pixel pct={pct:.2f}"
        if self._sampling and self._sampling.enabled:
            cur_path = pathlib.Path(tempfile.gettempdir()) / f"luna_regr_{uuid.uuid4().hex}.png"
            cur_path.write_bytes(current)
            try:
                hint = semantic_hint or meta.get("semantic_hint", "what is different visually")
                verdict = await self._sampling.verify_visual_diff(
                    str(baseline_path), str(cur_path), hint
                )
                return f"DIFF pixel pct={pct:.2f}\nsemantic: {verdict}"
            finally:
                cur_path.unlink(missing_ok=True)
        return f"DIFF pixel pct={pct:.2f} (semantic disabled)"

    async def visual_baseline_list(self, build_hash: str = "") -> str:
        """List all baselines for the current (or given) build."""
        bh = build_hash or await get_build_hash(self._bridge)
        names = self._store.list(bh)
        if not names:
            return f"(none) build={bh}"
        return f"build={bh}\n" + "\n".join(f"  {n}" for n in names)

    async def visual_baseline_invalidate(self, name: str = "", build_hash: str = "") -> str:
        """Delete one or all baselines for the current (or given) build."""
        bh = build_hash or await get_build_hash(self._bridge)
        count = self._store.invalidate(bh, name=name)
        if name:
            return f"invalidated '{name}' ({count} files) for build {bh}"
        return f"invalidated all baselines ({count} files) for build {bh}"


def register_regression_tools(mcp, get_bridge, store: BaselineStore,
                               sampling, *, exposed: set = frozenset()):
    """Register regression tools with MCP. Returns {name: (fn, params)} for batch."""
    from ..tools import maybe_expose

    def _get_tools() -> RegressionTools:
        t = RegressionTools(bridge=get_bridge(), store=store, sampling=sampling)
        return t

    async def visual_baseline_save(name: str, mask_zones: str = "",
                                   semantic_hint: str = "",
                                   pixel_threshold: float = 1.0) -> str:
        """Capture screenshot and save as named baseline for visual regression."""
        return await _get_tools().visual_baseline_save(
            name, mask_zones=mask_zones, semantic_hint=semantic_hint,
            pixel_threshold=pixel_threshold)
    maybe_expose(mcp, visual_baseline_save, exposed, read_only=False)

    async def visual_baseline_check(name: str, semantic_hint: str = "") -> str:
        """Compare current screenshot to saved baseline. Returns PASS or DIFF."""
        return await _get_tools().visual_baseline_check(name, semantic_hint=semantic_hint)
    maybe_expose(mcp, visual_baseline_check, exposed)

    async def visual_baseline_list(build_hash: str = "") -> str:
        """List all baselines for the current or given build hash."""
        return await _get_tools().visual_baseline_list(build_hash=build_hash)
    maybe_expose(mcp, visual_baseline_list, exposed)

    async def visual_baseline_invalidate(name: str = "", build_hash: str = "") -> str:
        """Delete one or all baselines for the current or given build hash."""
        return await _get_tools().visual_baseline_invalidate(name=name, build_hash=build_hash)
    maybe_expose(mcp, visual_baseline_invalidate, exposed, read_only=False)

    return {
        "visual_baseline_save": (visual_baseline_save, None),
        "visual_baseline_check": (visual_baseline_check, None),
        "visual_baseline_list": (visual_baseline_list, None),
        "visual_baseline_invalidate": (visual_baseline_invalidate, None),
    }
