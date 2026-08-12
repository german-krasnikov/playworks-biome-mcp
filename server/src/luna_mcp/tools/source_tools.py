from mcp.server.fastmcp.exceptions import ToolError

from . import maybe_expose


def register_source_tools(mcp, source_mapper_fn, *, exposed: set = frozenset()):
    """Register source mapping MCP tools."""

    async def resolve_stack_trace(stack_text: str) -> str:
        """Map JS error stack trace to C# source. Paste the full stack trace."""
        mapper = source_mapper_fn()
        try:
            return await mapper.resolve_stack(stack_text)
        except Exception as e:
            raise ToolError(f"Failed to resolve stack: {e}")
    maybe_expose(mcp, resolve_stack_trace, exposed)

    async def get_source_context(class_name: str, method_name: str = "", lines_around: int = 5) -> str:
        """Show transpiled JS around a C# method. Uses Luna comment markers."""
        mapper = source_mapper_fn()
        try:
            return await mapper.get_source_context(class_name, method_name, lines_around)
        except Exception as e:
            raise ToolError(f"Failed to get source context: {e}")
    maybe_expose(mcp, get_source_context, exposed)

    async def find_method(class_name: str, method_name: str = "") -> str:
        """Find JS location of a transpiled C# method in UnityScriptsCompiler.js."""
        mapper = source_mapper_fn()
        try:
            return await mapper.find_method(class_name, method_name)
        except Exception as e:
            raise ToolError(f"Failed to find method: {e}")
    maybe_expose(mcp, find_method, exposed)

    return {
        "resolve_stack_trace": (resolve_stack_trace, None),
        "get_source_context": (get_source_context, None),
        "find_method": (find_method, None),
    }
