from mcp.server.fastmcp.exceptions import ToolError

from . import maybe_expose

_require_debugger = None


def register_debugger_tools(mcp, require_debugger_fn, *, exposed: set = frozenset()):
    """Register debugger MCP tools on the given FastMCP instance."""
    global _require_debugger
    _require_debugger = require_debugger_fn

    async def set_breakpoint(file: str, line: int) -> str:
        """Set JS breakpoint. file=URL regex, line=1-indexed. Returns breakpoint ID."""
        dbg = await _require_debugger()
        try:
            bp_id = await dbg.set_breakpoint(file, line)
            return f"Breakpoint set: {bp_id}"
        except Exception as e:
            raise ToolError(f"Failed to set breakpoint: {e}")
    maybe_expose(mcp, set_breakpoint, exposed)

    async def remove_breakpoint(breakpoint_id: str) -> str:
        """Remove a breakpoint by ID."""
        dbg = await _require_debugger()
        try:
            await dbg.remove_breakpoint(breakpoint_id)
            return f"Breakpoint removed: {breakpoint_id}"
        except Exception as e:
            raise ToolError(f"Failed to remove breakpoint: {e}")
    maybe_expose(mcp, remove_breakpoint, exposed)

    async def debug_pause() -> str:
        """Pause JS execution."""
        dbg = await _require_debugger()
        try:
            await dbg.pause()
            return "Paused"
        except Exception as e:
            raise ToolError(f"Failed to pause: {e}")
    maybe_expose(mcp, debug_pause, exposed)

    async def debug_resume() -> str:
        """Resume JS execution."""
        dbg = await _require_debugger()
        try:
            await dbg.resume()
            return "Resumed"
        except Exception as e:
            raise ToolError(f"Failed to resume: {e}")
    maybe_expose(mcp, debug_resume, exposed)

    async def get_call_stack() -> str:
        """Get call stack when paused. Returns formatted text."""
        dbg = await _require_debugger()
        return dbg.get_call_stack()
    maybe_expose(mcp, get_call_stack, exposed)

    async def get_scope_variables(frame_index: int = 0) -> str:
        """Get local variables at a call frame. frame_index=0 is current frame."""
        dbg = await _require_debugger()
        try:
            return await dbg.get_scope_variables(frame_index)
        except Exception as e:
            raise ToolError(f"Failed to get scope variables: {e}")
    maybe_expose(mcp, get_scope_variables, exposed)

    # Export for testing and batch registration
    return {
        "set_breakpoint": (set_breakpoint, None),
        "remove_breakpoint": (remove_breakpoint, None),
        "debug_pause": (debug_pause, None),
        "debug_resume": (debug_resume, None),
        "get_call_stack": (get_call_stack, None),
        "get_scope_variables": (get_scope_variables, None),
    }
