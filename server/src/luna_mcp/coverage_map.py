"""Pure coverage mapper — maps dead JS ranges to C# Class.Method via source markers."""
from __future__ import annotations

import re

from luna_mcp.cdp_domains import offset_to_line, truncate_lines

_MARKER_RE = re.compile(r"/\*([\w.]+) start\b")


def _build_marker_index(source: str) -> list[tuple[int, str]]:
    """Return sorted list of (line, class.method) from source markers."""
    markers = []
    for m in _MARKER_RE.finditer(source):
        line = offset_to_line(source, m.start())
        markers.append((line, m.group(1)))
    return sorted(markers, key=lambda x: x[0])


def _enclosing_marker(markers: list[tuple[int, str]], dead_line: int) -> str | None:
    """Find enclosing C# marker: largest start_line <= dead_line."""
    result = None
    for start_line, name in markers:
        if start_line <= dead_line:
            result = name
        else:
            break
    return result


def _is_dead_fn(fn: dict) -> bool:
    """A function is DEAD if ALL its ranges have count==0."""
    ranges = fn.get("ranges", [])
    return bool(ranges) and all(r.get("count", 1) == 0 for r in ranges)


async def map_dead_functions(
    coverage_result: list[dict],
    require_source_mapper,
    top: int = 30,
) -> str:
    """Map dead coverage ranges to C# methods via source markers."""
    mapper = require_source_mapper()
    if mapper is None:
        return "[DEGRADED] source mapper not available"

    # Find UnityScriptsCompiler script in coverage result
    script_entry = None
    sid = mapper.find_script_id("UnityScriptsCompiler")
    for entry in coverage_result:
        if (sid and entry.get("scriptId") == sid) or "UnityScriptsCompiler" in entry.get("url", ""):
            script_entry = entry
            break

    if script_entry is None:
        return "[DEGRADED] UnityScriptsCompiler not in coverage result"

    # Get actual script id from entry (might differ if sid search failed)
    actual_sid = script_entry.get("scriptId") or sid
    if not actual_sid:
        return "[DEGRADED] no scriptId for UnityScriptsCompiler"

    source = await mapper.get_source(actual_sid)
    markers = _build_marker_index(source)

    dead_methods: dict[str, int] = {}
    unmapped_count = 0

    for fn in script_entry.get("functions", []):
        if not _is_dead_fn(fn):
            continue
        start_offset = fn.get("ranges", [{}])[0].get("startOffset", 0)
        end_offset = fn.get("ranges", [{}])[0].get("endOffset", start_offset)
        span = end_offset - start_offset
        dead_line = offset_to_line(source, start_offset)
        if markers:
            method = _enclosing_marker(markers, dead_line)
            if method:
                dead_methods[method] = dead_methods.get(method, 0) + span
                continue
        unmapped_count += span

    if not dead_methods and unmapped_count == 0:
        return "OK no dead code found"

    lines = []
    for method, span in sorted(dead_methods.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{method}  DEAD  ({span}B)")

    if not markers and unmapped_count > 0:
        return f"UNMAPPED: {unmapped_count} dead ranges (no source markers — build minified?)"

    if unmapped_count > 0:
        lines.append(f"UNMAPPED: {unmapped_count}B")

    return "\n".join(truncate_lines(lines, top))
