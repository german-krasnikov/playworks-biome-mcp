"""Template MCP tools: template, template_list, template_save."""
from __future__ import annotations
import pathlib
from luna_mcp.templates.registry import TemplateRegistry, _BUNDLED_DIR, _USER_DIR
from luna_mcp.templates.placeholders import expand, parse_args, PlaceholderError
from luna_mcp.tools.batch import execute_batch
from . import maybe_expose


def _make_tools(bundled_dir=_BUNDLED_DIR, user_dir=_USER_DIR):
    reg = TemplateRegistry(bundled_dir=bundled_dir, user_dir=user_dir)

    async def template(name: str, args: str = "", mode: str = "continue") -> str:
        """Expand a batch template with args and execute it. args format: 'key=value key=value'."""
        t = reg.load(name)
        if t is None:
            return f"[INVALID: template '{name}' not found. Try template_list().]"
        kw = parse_args(args)
        try:
            body = expand(t.body, kw)
        except PlaceholderError as e:
            return f"[INVALID: {e}]"
        cmds = "\n".join(
            ln for ln in body.split("\n")
            if ln.strip() and not ln.strip().startswith("#")
        )
        result = await execute_batch(cmds, mode=mode)
        return f"{result}\n[via template:{name}]"

    async def template_list(filter_str: str = "") -> str:
        """List available templates. Optionally filter by name substring."""
        items = reg.list_all(filter_str)
        if not items:
            return "no templates found"
        lines = [f"{t.name} | params={','.join(t.params) or '-'} | {t.desc}" for t in items]
        return "\n".join(lines)

    async def template_save(name: str, body: str, overwrite: bool = False) -> str:
        """Save a custom template to user templates dir (~/.playworks-biome-mcp/templates/)."""
        try:
            p = reg.save_user(name, body, overwrite)
            return f"saved: {p}"
        except (ValueError, FileExistsError) as e:
            return f"[INVALID: {e}]"

    return {
        "template": template,
        "template_list": template_list,
        "template_save": template_save,
    }


def register_template_tools(mcp, *, exposed: set = frozenset()):
    tools = _make_tools()
    write_tools = {"template_save"}
    for fn_name, fn in tools.items():
        maybe_expose(mcp, fn, exposed, name=fn_name, read_only=fn_name not in write_tools)
    return {name: (fn, None) for name, fn in tools.items()}
