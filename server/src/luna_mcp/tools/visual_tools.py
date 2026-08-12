from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from . import maybe_expose
from .modify_tools import _parse_value


def register_visual_tools(mcp, call_fn, bridge_getter, *, exposed: set = frozenset()):
    """Register visual debugging tools. Returns {name: (fn, params)} for batch."""

    async def pause_game() -> str:
        """Freeze the scene (timeScale=0). Objects stop moving/animating."""
        return await call_fn("pauseGame")
    maybe_expose(mcp, pause_game, exposed)

    async def resume_game() -> str:
        """Resume the scene (timeScale=1)."""
        return await call_fn("resumeGame")
    maybe_expose(mcp, resume_game, exposed)

    async def get_game_state() -> str:
        """Current game state: timeScale, paused status, editor camera."""
        return await call_fn("getGameState")
    maybe_expose(mcp, get_game_state, exposed)

    async def get_layers() -> str:
        """List all Unity layers and sorting layers. Use to check culling mask issues."""
        return await call_fn("getLayers")
    maybe_expose(mcp, get_layers, exposed)

    async def diagnose_object(path: str) -> str:
        """One-shot visual diagnostic for a GameObject: active chain, transform, renderer, materials, plus any matching console errors. Use when an object isn't rendering or behaving as expected. For a full component dump, use get_object_detail instead."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        diag = await call_fn("diagnoseObject", path)
        msgs = bridge.get_console_messages(100)
        obj_name = path.split("/")[-1].lower()
        errors = [m for m in msgs if m["level"] == "E" and obj_name in m["text"].lower()]
        suffix = "".join("\n[!!] console: " + e["text"][:120] for e in errors[-3:]) if errors \
            else '\n[--] no console errors mentioning "' + path.split("/")[-1] + '"'
        return diag + suffix
    maybe_expose(mcp, diagnose_object, exposed)

    async def get_materials(path: str, include_children: bool = False) -> str:
        """List materials on object (and optionally children) with shader names."""
        return await call_fn("getMaterials", path, include_children)
    maybe_expose(mcp, get_materials, exposed)

    async def get_animator_state(path: str) -> str:
        """Inspect animator: layers, active states, transitions, parameters. Requires Luna Debugger."""
        return await call_fn("getAnimatorState", path)
    maybe_expose(mcp, get_animator_state, exposed)

    async def set_animator_param(path: str, param: str, value: str, is_trigger: bool = False) -> str:
        """Set animator parameter or trigger. Requires Luna Debugger.
        value: auto-converted (true/false/number/string). is_trigger=true for triggers."""
        parsed = _parse_value(value)
        return await call_fn("setAnimatorParam", path, param, parsed, is_trigger)
    maybe_expose(mcp, set_animator_param, exposed)

    async def toggle_editor_camera(enable: bool | None = None) -> str:
        """Toggle free-fly editor camera. WASD+mouse to navigate. Requires Luna Debugger.
        enable=true/false, or omit to toggle."""
        if enable is None:
            return await call_fn("toggleEditorCamera")
        return await call_fn("toggleEditorCamera", enable)
    maybe_expose(mcp, toggle_editor_camera, exposed)

    async def get_shader_report() -> str:
        """List all shaders: name, pass count, compilation errors. Finds missing shaders."""
        return await call_fn("getShaderReport")
    maybe_expose(mcp, get_shader_report, exposed)

    async def audit_materials() -> str:
        """Scan ALL renderers in scene for material issues: null material, fallback shader, missing textures."""
        return await call_fn("auditMaterials")
    maybe_expose(mcp, audit_materials, exposed)

    async def show_collider(path: str) -> str:
        """Show semi-transparent collider overlay (Box/Sphere/Capsule). Requires Luna Debugger + editor camera."""
        return await call_fn("showCollider", path)
    maybe_expose(mcp, show_collider, exposed)

    async def hide_collider() -> str:
        """Hide the collider overlay shown by show_collider."""
        return await call_fn("hideCollider")
    maybe_expose(mcp, hide_collider, exposed)

    async def set_field(path: str, component: str, field: str, value: str, field_type: str) -> str:
        """Set any component field via pc.Debugger.Inspector. field_type: number/boolean/string/Vector/Color/Enum."""
        return await call_fn("setField", path, component, field, value, field_type)
    maybe_expose(mcp, set_field, exposed)

    async def edit_animator_state(path: str, state_hash: str, prop: str, value: str) -> str:
        """Edit individual animator state properties (speed, cycleOffset, mirror, writeDefaults).
        state_hash: hash from get_animator_state. Requires Luna Debugger."""
        return await call_fn("editAnimatorState", path, state_hash, prop, value)
    maybe_expose(mcp, edit_animator_state, exposed)

    async def get_deep_link(path: str, component: str = "") -> str:
        """Return deep link URL for a GameObject or component (gameobject:guid& / component:guid&...)."""
        return await call_fn("getDeepLink", path, component)
    maybe_expose(mcp, get_deep_link, exposed)

    async def toggle_profiler(enable: bool | None = None) -> str:
        """Toggle FPS/ms/memory stats overlay (stats.js). Requires Luna Debugger. Omit enable to toggle."""
        if enable is None:
            return await call_fn("toggleProfiler")
        return await call_fn("toggleProfiler", enable)
    maybe_expose(mcp, toggle_profiler, exposed)

    async def show_collider_overlay(path: str) -> str:
        """Show collider shapes as colored overlays on object (visible on screenshots)."""
        return await call_fn("showColliderOverlay", path)
    maybe_expose(mcp, show_collider_overlay, exposed)

    async def show_all_collider_overlays(max_count: int = 20, skip_ground: bool = True) -> str:
        """Show all collider shapes in scene. skip_ground=true skips Ground/Floor + colliders >20 units."""
        return await call_fn("showAllColliderOverlays", min(max_count, 50), skip_ground)
    maybe_expose(mcp, show_all_collider_overlays, exposed)

    async def hide_collider_overlays() -> str:
        """Remove all debug collider overlays."""
        return await call_fn("hideColliderOverlays")
    maybe_expose(mcp, hide_collider_overlays, exposed)

    async def visual_summary(detail: str = "compact") -> str:
        """Zero-cost text 'screenshot'. detail: compact|full|ui_only.
        Returns visible objects with screen-space buckets, UI text, end-card state.
        ~50-200 tokens vs 5-15k for a PNG screenshot."""
        return await call_fn("visualSummary", detail)
    maybe_expose(mcp, visual_summary, exposed)

    async def visual_diff(prev_id: str = "") -> str:
        """Diff against previous visual_summary snapshot.
        Empty prev_id = vs last cached (5s TTL). Returns changed/added/removed objects."""
        return await call_fn("visualDiff", prev_id)
    maybe_expose(mcp, visual_diff, exposed)

    return {
        "pause_game": (pause_game, {}),
        "resume_game": (resume_game, {}),
        "get_game_state": (get_game_state, {}),
        "get_layers": (get_layers, {}),
        "diagnose_object": (diagnose_object, {"path": str}),
        "get_materials": (get_materials, {"path": str, "include_children": bool}),
        "get_animator_state": (get_animator_state, {"path": str}),
        "set_animator_param": (set_animator_param, {"path": str, "param": str, "value": str, "is_trigger": bool}),
        "toggle_editor_camera": (toggle_editor_camera, {"enable": bool}),
        "get_shader_report": (get_shader_report, {}),
        "audit_materials": (audit_materials, {}),
        "show_collider": (show_collider, {"path": str}),
        "hide_collider": (hide_collider, {}),
        "set_field": (set_field, {"path": str, "component": str, "field": str, "value": str, "field_type": str}),
        "edit_animator_state": (edit_animator_state, {"path": str, "state_hash": str, "prop": str, "value": str}),
        "get_deep_link": (get_deep_link, {"path": str, "component": str}),
        "toggle_profiler": (toggle_profiler, {"enable": bool}),
        "show_collider_overlay": (show_collider_overlay, {"path": str}),
        "show_all_collider_overlays": (show_all_collider_overlays, {"max_count": int, "skip_ground": bool}),
        "hide_collider_overlays": (hide_collider_overlays, {}),
        "visual_summary": (visual_summary, {"detail": str}),
        "visual_diff": (visual_diff, {"prev_id": str}),
    }
