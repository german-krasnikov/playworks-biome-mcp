from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

# Migration MUST run before any other luna_mcp import touches data_dir()
# (e.g. record_tools creates ~/.playworks-biome-mcp/recordings/ at import
# time, which would make the migration a permanent no-op if it ran first).
from luna_mcp.config import data_dir as _cfg_data_dir
from luna_mcp.config import migrate_data_dir as _migrate_data_dir

_migrate_data_dir()

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

import luna_mcp.schema_guard as _sg_module
import luna_mcp.tools.record_tools as _record_mod

from .budget import BudgetTracker, ToolRouter
from .budget.metrics import MetricsRegistry
from .budget.sinks import JsonlSink, NullSink
from .cdp_bridge import CDPBridge
from .composition import apply_composition
from .debugger import Debugger
from .degradation import GracefulDegradation
from .hinter import ToolHinter
from .lessons.seeds import seed_default
from .lessons.store import LessonStore
from .lessons.typemap_seeds import seed_typemap_lessons
from .lifespan import wire_features
from .luna_runtime import LunaRuntime
from .reflect import with_reflect
from .schema_cache import SchemaCache
from .schema_guard import SchemaGuard
from .server_helpers import (  # noqa: F401 — _maybe_inject_lesson unused here but re-exported; _LESSON_INJECT_CMDS used at line 308
    _LESSON_INJECT_CMDS,
    _maybe_inject_lesson,
)
from .source_mapper import SourceMapper
from .tools.batch import execute_batch, register_batch_tool
from .tools.modify_tools import _parse_value  # noqa: F401 — used by tests
from .typemap_resolver import TypemapResolver
from .watchdog.scanner import Watchdog
from .wiring import register_all_tools

logger = logging.getLogger(__name__)
bridge: CDPBridge | None = None
runtime: LunaRuntime | None = None
debugger: Debugger | None = None
source_mapper: SourceMapper | None = None
typemap_resolver: TypemapResolver | None = None
_sampling = None
_schema_cache: SchemaCache | None = None
_metrics: MetricsRegistry = MetricsRegistry(
    cap=int(os.environ.get("LUNA_BUDGET_CAP", "30000")),
    sink=None,
)
_budget_tracker: BudgetTracker = _metrics
from .budget.calibrator import CostCalibrator as _CostCalibrator

_calibrator: _CostCalibrator = _CostCalibrator()
_budget_router: ToolRouter = ToolRouter(_metrics, calibrator=_calibrator)
_lessons_store: LessonStore | None = None
_watchdog: Watchdog | None = None
from .watchdog.brain_scan import BrainScanner as _BrainScanner

_brain_scanner: "_BrainScanner | None" = None
_hinter: ToolHinter = ToolHinter()
_degradation: GracefulDegradation | None = None

# Recorder singleton — shared with record_tools module
from .record.recorder import Recorder as _Recorder

_rec_data_dir = _cfg_data_dir()
_recorder = _Recorder(_rec_data_dir / "recordings")
_record_mod._recorder = _recorder


async def _ensure_connected() -> None:
    if bridge is None:
        raise ToolError("Server not initialized")
    if bridge.connected:
        return
    try:
        await bridge.connect(os.environ.get("LUNA_PAGE_FILTER"))
        await bridge.enable_all_domains()
    except Exception as e:
        raise ToolError(f"Chrome not connected: {e}. Start Chrome with --remote-debugging-port=9222")


async def _send(expression: str, timeout: float = 30.0) -> str:
    await _ensure_connected()
    s = expression[:100] + ("..." if len(expression) > 100 else "")
    try:
        return await bridge.eval(expression, timeout=timeout)
    except RuntimeError as e:
        raise ToolError(f"JS error: {e}\n  expr: {s}")
    except Exception as e:
        raise ToolError(f"CDP error: {e}\n  expr: {s}")


async def _call(method: str, *args) -> str:
    await _ensure_connected()
    if runtime is None:
        raise ToolError("Server not initialized")
    s = f"__luna_mcp.{method}(...)"[:100]
    try:
        return await runtime.call(method, *args)
    except RuntimeError as e:
        raise ToolError(f"JS error: {e}\n  expr: {s}")
    except Exception as e:
        raise ToolError(f"CDP error: {e}\n  expr: {s}")


async def _require_debugger() -> "Debugger":
    await _ensure_connected()
    if debugger is None:
        raise ToolError("Server not initialized")
    return debugger


def _require_source_mapper() -> "SourceMapper":
    if source_mapper is None:
        raise ToolError("Server not initialized")
    return source_mapper


def _init_sink():
    if os.environ.get("LUNA_MCP_METRICS") == "1":
        return JsonlSink(_cfg_data_dir() / "metrics.jsonl")
    return NullSink()


# Backward-compat adapters (used by existing tests)
from .composition import _gated as _comp_gated
from .composition import _observe as _comp_observe


def _gated(name: str, fn, router, tracker, all_tools_dict: dict):
    return _comp_gated(name, fn, router, tracker, all_tools_dict, observe_fn=_observe)


async def _observe(name: str, fn, kw: dict, args: tuple) -> str:
    return await _comp_observe(name, fn, kw, args, _metrics, _calibrator, _watchdog)


@asynccontextmanager
async def lifespan(app):
    global bridge, runtime, debugger, source_mapper, typemap_resolver, _schema_cache
    global _lessons_store, _watchdog, _degradation, _sampling
    bridge = CDPBridge(port=int(os.environ.get("LUNA_CDP_PORT", "9222")))
    runtime = LunaRuntime(bridge)
    debugger = Debugger(bridge)
    typemap_resolver = TypemapResolver()
    source_mapper = SourceMapper(bridge, debugger, typemap_resolver)
    _schema_cache = SchemaCache()
    _sg_module._GUARD = SchemaGuard(_schema_cache, typemap_resolver, _call)
    _budget_mode = os.environ.get("LUNA_BUDGET_MODE", "work")
    if _budget_mode == "auto":
        from luna_mcp.budget import _init_budget_auto
        _auto_tracker, _auto_router = _init_budget_auto()
        _metrics.cap = _auto_tracker.cap
        _metrics._history = _auto_tracker._history
        _budget_router._p_success = _auto_router._p_success
    else:
        from luna_mcp.budget.tracker import PRESETS as _PRESETS
        _metrics.cap = _PRESETS.get(_budget_mode, 30_000)
    _metrics.reset()
    _metrics._sink = _init_sink()
    if os.environ.get("LUNA_MCP_LESSONS", "1") != "0":
        _lessons_store = LessonStore(_cfg_data_dir() / "lessons.db")
        seed_default(_lessons_store)
        seed_typemap_lessons(_lessons_store)
    _watchdog = Watchdog(_call, _metrics, get_bridge=lambda: bridge) if os.environ.get("LUNA_MCP_WATCHDOG") == "1" else None
    global _brain_scanner
    _brain_scanner = _BrainScanner()
    _degradation = GracefulDegradation(lambda: bridge, _metrics, lambda: typemap_resolver)

    wire_features(
        call_fn=_call, sampling=_sampling, ping_fn=ping,
        lessons_store=_lessons_store,
        rec_data_dir=_rec_data_dir, build_semantic=_build_semantic,
        pc_validator=_pc_validator, metrics=_metrics,
        all_tools=_all_tools,
    )

    async def _on_reconnect():
        import luna_mcp.build_id as _build_id
        _build_id.reset_cache()
        runtime._injected = False
        debugger._enabled = False
        source_mapper._source_cache.clear()
        if _schema_cache:
            _schema_cache.invalidate_all()
        try:
            await bridge.enable_all_domains()
        except Exception:
            logger.debug("enable_all_domains failed on reconnect", exc_info=True)

    bridge._on_reconnect = _on_reconnect

    from .tools.som_tools import _marker_map as _som_map
    async def _on_frame_navigated():
        _som_map.clear()
    bridge._on_frame_navigated = _on_frame_navigated

    try:
        await bridge.connect(os.environ.get("LUNA_PAGE_FILTER"))
        try:
            await bridge.enable_all_domains()
        except Exception as e:
            logger.warning("enable domains failed: %s", e)
    except Exception as e:
        logger.warning("Chrome not available at startup: %s", e)
    try:
        yield
    finally:
        if _recorder.active:
            _recorder.stop()
        if _watchdog:
            _watchdog.cancel_all()
        if _lessons_store:
            _lessons_store.close()
        if hasattr(_budget_tracker, "_history"):
            _budget_tracker.on_shutdown(_budget_tracker._history)
            _budget_tracker._history.close()
        _metrics.close()
        await bridge.close()


mcp = FastMCP("PlayworksBiomeMCP", lifespan=lifespan)


@mcp.tool()
async def connect(port: int = 0, page_filter: str = "") -> str:
    """Connect (or reconnect) to Chrome remote debugging. port=0 uses default (9222 or LUNA_CDP_PORT).
    Use when Chrome has restarted or you need to switch to a different page. page_filter is a URL substring."""
    if bridge is None:
        raise ToolError("Server not initialized")
    if bridge.connected:
        await bridge.close()
    if port > 0:
        bridge._port = port
    try:
        pf = page_filter or os.environ.get("LUNA_PAGE_FILTER")
        await bridge.connect(pf)
        await bridge.enable_all_domains()
        if runtime:
            runtime._injected = False
            try:
                await bridge.eval("var f=document.querySelector('iframe');if(f&&f.contentWindow)f.contentWindow.__luna_mcp=undefined")
            except Exception:
                logger.debug("luna_mcp iframe reset failed", exc_info=True)
    except Exception as e:
        raise ToolError(f"Failed to connect: {e}")
    return f"Connected to Chrome on port {bridge._port}"


@mcp.tool()
async def ping() -> str:
    """Verify Chrome connection and Luna helpers are injected in the iframe. Returns 'pong' or 'no helpers'. Use before other tools to confirm the session is live."""
    return await _send(
        "typeof document.querySelector('iframe')"
        "?.contentWindow?.__luna_mcp !== 'undefined' ? 'pong' : 'no helpers'"
    )


# Register all tool groups
_all_tools, _sampling, _build_semantic, _pc_validator = register_all_tools(
    mcp=mcp,
    call_fn=_call,
    send_fn=_send,
    get_bridge=lambda: bridge,
    ensure_connected=_ensure_connected,
    require_debugger=_require_debugger,
    require_source_mapper=_require_source_mapper,
    get_typemap=lambda: typemap_resolver,
    budget_tracker=_budget_tracker,
    budget_router=_budget_router,
    get_brain_scanner=lambda: _brain_scanner,
)

# Composition stack constants
_REFLECT_CMDS = {"set_property", "set_transform", "eval_js"}
_BUDGET_OWN = {"analyze_visual", "set_budget", "get_budget_status", "ping", "mcp_stats"}
_MUTATION_CMDS = {"set_property", "set_transform", "get_component"}
_RECORDER_SKIP = frozenset({
    "record_start", "record_stop", "record_list", "replay", "record_diff",
    "mcp_stats", "set_budget", "get_budget_status",
})
_HINTER_SKIP = {"connect", "ping"} | _BUDGET_OWN

_batch_registry = apply_composition(
    _all_tools,
    budget_router=_budget_router,
    budget_tracker=_budget_tracker,
    get_metrics=lambda: _metrics,
    get_calibrator=lambda: _calibrator,
    get_watchdog=lambda: _watchdog,
    recorder=_recorder,
    get_degradation=lambda: _degradation,
    get_lessons_store=lambda: _lessons_store,
    hinter=_hinter,
    guard_module=_sg_module,
    reflect_fn=with_reflect,
    lesson_inject_cmds=_LESSON_INJECT_CMDS,
    reflect_cmds=_REFLECT_CMDS,
    budget_own=_BUDGET_OWN,
    mutation_cmds=_MUTATION_CMDS,
    recorder_skip=_RECORDER_SKIP,
    hinter_skip=_HINTER_SKIP,
)

for _name, (_fn, _params) in _batch_registry.items():
    register_batch_tool(_name, _fn, _params)

register_batch_tool("ping", ping, {})
globals().update({name: fn for name, (fn, _) in _all_tools.items()})


def _make_batch_help(registry: dict) -> str:
    lines = []
    for name in sorted(registry.keys()):
        _, params = registry[name]
        args = " ".join(f"{k}=" for k in params) if params else ""
        lines.append(f"  {name} {args}".rstrip())
    return "\n".join(lines)


_batch_help = _make_batch_help(_all_tools)


@mcp.tool()
async def batch(commands: str, mode: str = "continue") -> str:
    """Execute multiple commands in one call. One command per line: 'cmd key=value'.
    mode: continue (default) or stop on first error."""
    return await execute_batch(commands, mode)

batch.__doc__ += f"\n\nALL COMMANDS:\n{_batch_help}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
