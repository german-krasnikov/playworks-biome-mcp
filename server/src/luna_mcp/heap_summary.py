"""Pure heap profile summarizer — no CDP, no state."""
from __future__ import annotations

from luna_mcp.cdp_domains import truncate_lines


def _flatten(node: dict, acc: dict) -> None:
    """Recursively accumulate selfSize per callFrame."""
    frame = node.get("callFrame", {})
    key = (
        frame.get("functionName", "(anonymous)"),
        frame.get("url", ""),
        frame.get("lineNumber", 0),
    )
    acc[key] = acc.get(key, 0) + node.get("selfSize", 0)
    for child in node.get("children", []):
        _flatten(child, acc)


def summarize(profile: dict, top: int = 15) -> str:
    """Summarize heap sample profile into top-N allocators by selfSize."""
    head = profile.get("head")
    if not head:
        return "(no allocation samples — try longer duration)"
    acc: dict = {}
    _flatten(head, acc)
    if not acc:
        return "(no allocation samples — try longer duration)"
    sorted_entries = sorted(acc.items(), key=lambda x: x[1], reverse=True)
    lines = []
    for (name, url, line), size_bytes in sorted_entries:
        if size_bytes == 0:
            continue
        kb = size_bytes / 1024
        loc = f"{url}:{line}" if url else "(native)"
        lines.append(f"{name}  {kb:.1f}KB  ({loc})")
    if not lines:
        return "(no allocation samples — try longer duration)"
    return "\n".join(truncate_lines(lines, top))
