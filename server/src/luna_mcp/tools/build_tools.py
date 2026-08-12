"""Static build analyzer — reads Luna build files from disk. No Chrome needed."""
from __future__ import annotations

from pathlib import Path

from . import maybe_expose
from .build_helpers import (
    biggest_files,
    fmt_kb,
    fmt_playground,
    read_json,
    recommendations,
    stage3,
    stage4,
    walk_sizes,
)


async def analyze_build(build_path: str) -> str:
    """Analyze Luna build output. build_path = Unity project root with LunaTemp/."""
    luna_temp = Path(build_path) / "LunaTemp"
    if not luna_temp.exists():
        return f"error: LunaTemp not found at {build_path}"

    s4 = stage4(build_path)
    lines = [f"BUILD ANALYSIS: {build_path}"]

    cfg = read_json(s4 / "luna.json") or {}
    lines += [f"Platform: {cfg.get('platform', 'unknown')}", f"Luna SDK: {cfg.get('version', 'unknown')}", ""]

    size_map = walk_sizes(s4)
    total = sum(size_map.values())
    compressed = int(total * 0.118)

    js_bytes = size_map.get(".js", 0)
    tex_bytes = sum(size_map.get(e, 0) for e in (".png", ".jpg", ".jpeg", ".webp", ".ktx"))
    audio_bytes = sum(size_map.get(e, 0) for e in (".mp3", ".ogg", ".wav", ".m4a"))
    font_bytes = size_map.get(".ttf", 0) + size_map.get(".otf", 0)
    json_bytes = size_map.get(".json", 0)
    js_pct = int(js_bytes * 100 / total) if total else 0

    lines.append("SIZE BREAKDOWN:")
    lines.append(f"  Total: {fmt_kb(total)} (develop) / ~{fmt_kb(compressed)} (estimated compressed)")

    js_top = biggest_files(s4, ".js")
    lines.append(f"  Scripts: {fmt_kb(js_bytes)} ({js_pct}%)")
    for name, sz in js_top:
        flag = "[!!] " if sz > 500 * 1024 else "     "
        lines.append(f"    {flag}{name:<40} {fmt_kb(sz)}")

    tex_count = sum(1 for f in s4.rglob("*") if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".ktx"))
    tex_top = biggest_files(s4, ".png")
    lines.append(f"  Textures: {fmt_kb(tex_bytes)} ({tex_count} files)")
    for name, sz in tex_top:
        flag = "[!!] " if "LiberationSans" in name or "EmojiOne" in name else "     "
        lines.append(f"    {flag}{name:<40} {fmt_kb(sz)}")

    if audio_bytes:
        lines.append(f"  Audio: {fmt_kb(audio_bytes)}")
    if font_bytes:
        lines.append(f"  Fonts: {fmt_kb(font_bytes)}")
    if json_bytes:
        lines.append(f"  Data: {fmt_kb(json_bytes)} (JSON config)")

    pg = read_json(s4 / "js" / "playground.json") or {}
    pg_fields = pg.get("fields", {})
    field_lines = fmt_playground(pg_fields)
    total_fields = sum(len(v) for v in pg_fields.values())
    lines += ["", f"PLAYGROUND FIELDS ({total_fields}):"] + (field_lines or ["  (none)"])

    shaders_path = s4 / "assets" / "shaders.json"
    shaders_data = read_json(shaders_path)
    shader_count = len(shaders_data) if isinstance(shaders_data, list) else 0
    shader_size = shaders_path.stat().st_size if shaders_path.exists() else 0
    lines += ["", f"SHADERS: {shader_count} compiled ({fmt_kb(shader_size)} total)"]

    recs = recommendations(js_top, tex_top, shader_count)
    lines += ["", "RECOMMENDATIONS:"]
    lines += recs if recs else ["  (none)"]

    return "\n".join(lines)


async def get_playground_fields(build_path: str) -> str:
    """List Playground Fields from build. For A/B testing."""
    s4 = stage4(build_path)
    pg_path = s4 / "js" / "playground.json"
    if not pg_path.exists():
        return f"no playground.json found at {pg_path}"

    pg = read_json(pg_path) or {}
    fields_map = pg.get("fields", {})
    field_lines = fmt_playground(fields_map)
    total = sum(len(v) for v in fields_map.values())
    return "\n".join([f"PLAYGROUND FIELDS ({total}):"] + (field_lines or ["  (none)"]))


async def get_build_assets(build_path: str, min_size_kb: int = 10) -> str:
    """List build assets sorted by size. Reads stats.json from stage3."""
    stats_path = stage3(build_path) / "stats.json"
    if not stats_path.exists():
        return f"no stats.json found at {stats_path}"

    data = read_json(stats_path) or {}
    assets = []
    for t in data.get("types", []):
        for a in t.get("assets", []):
            size_b = a.get("size", 0)
            if size_b >= min_size_kb * 1024:
                assets.append((a.get("title", "?"), size_b, a.get("path", "")))

    assets.sort(key=lambda x: -x[1])
    if not assets:
        return f"ASSETS (>{min_size_kb}KB):\n  (none)"

    lines = [f"ASSETS (>{min_size_kb}KB):"]
    for title, size_b, path in assets:
        lines.append(f"  {title:<30} {fmt_kb(size_b):<10}  {path}")
    return "\n".join(lines)


def register_build_tools(mcp, *, exposed: set = frozenset()):
    """Build analysis tools. No Chrome needed — reads files from disk."""

    async def analyze_build_tool(build_path: str) -> str:
        """Analyze a Luna build on disk (no Chrome needed). Reads LunaTemp/ for file sizes by category, shader count, playground fields, and optimization recommendations. build_path is the Unity project root containing LunaTemp/."""
        return await analyze_build(build_path)
    maybe_expose(mcp, analyze_build_tool, exposed, name="analyze_build")

    async def get_playground_fields_tool(build_path: str) -> str:
        """List all Playground Fields exposed in the build (used for A/B testing and network-side value overrides). Reads playground.json from the build output. Use to discover what parameters can be tuned without a rebuild."""
        return await get_playground_fields(build_path)
    maybe_expose(mcp, get_playground_fields_tool, exposed, name="get_playground_fields")

    async def get_build_assets_tool(build_path: str, min_size_kb: int = 10) -> str:
        """List individual build assets (textures, scripts, audio) sorted by size, filtered to ≥ min_size_kb. Reads webpack stats.json from stage3. Use to find the biggest contributors to build size before running optimize_build_size."""
        return await get_build_assets(build_path, min_size_kb)
    maybe_expose(mcp, get_build_assets_tool, exposed, name="get_build_assets")

    return {
        "analyze_build": (analyze_build_tool, None),
        "get_playground_fields": (get_playground_fields_tool, None),
        "get_build_assets": (get_build_assets_tool, None),
    }
