"""Hierarchy Distiller — Tier 1 stats + optional Tier 2 Haiku anomaly detection."""
from __future__ import annotations

import re
from collections import Counter

_COMP_RE = re.compile(r'\[([^\]]*)\]')
_INACTIVE_SUFFIX = re.compile(r'\s!$')


def distill_tier1(hierarchy: str) -> dict:
    """Parse hierarchy text → stats dict."""
    if not hierarchy.strip():
        return {"total": 0, "inactive": 0, "max_depth": 0, "components": Counter()}

    lines = hierarchy.strip().split("\n")
    total = len(lines)
    components: Counter = Counter()
    inactive = 0
    max_depth = 0

    for line in lines:
        depth = (len(line) - len(line.lstrip())) // 2
        max_depth = max(max_depth, depth)
        if _INACTIVE_SUFFIX.search(line):
            inactive += 1
        m = _COMP_RE.search(line)
        if m:
            for comp in m.group(1).split(", "):
                comp = comp.strip()
                if comp:
                    components[comp] += 1

    return {"total": total, "inactive": inactive, "max_depth": max_depth, "components": components}


def format_stats(stats: dict) -> str:
    """Format Tier 1 stats dict → human-readable text."""
    if stats["total"] == 0:
        return "Empty scene"
    top = stats["components"].most_common(10)
    lines = [
        f"Scene: {stats['total']} objects, depth {stats['max_depth']}, {stats['inactive']} inactive",
        "Components: " + ", ".join(f"{n}×{c}" for c, n in top),
    ]
    return "\n".join(lines)


async def distill(hierarchy: str, threshold: int = 50, sampling=None) -> str:
    """Main entry: stats-only or stats+Haiku summary."""
    lines = hierarchy.strip().split("\n") if hierarchy.strip() else []

    if not lines:
        return format_stats(distill_tier1(hierarchy))

    if len(lines) < threshold:
        return hierarchy

    stats = distill_tier1(hierarchy)
    tier1_text = format_stats(stats)

    if sampling is None:
        return tier1_text

    # Tier 2: Haiku anomaly detection
    preview = "\n".join(lines[:200])
    prompt = (
        f"Hierarchy stats:\n{tier1_text}\n\nFirst 200 lines:\n{preview}\n\n"
        "Identify structural anomalies and semantic groups in 3-5 bullet points."
    )
    try:
        summary = await sampling.plan(prompt, "Summarize scene hierarchy anomalies.")
        return f"{tier1_text}\n\n[ANOMALIES]\n{summary}"
    except Exception:
        return tier1_text
