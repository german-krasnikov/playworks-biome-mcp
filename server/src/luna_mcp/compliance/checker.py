"""F12 Compliance Checker — Tier 1 pure Python checks against ad network rules."""
from __future__ import annotations

from pathlib import Path

NETWORK_RULES: dict[str, dict] = {
    "meta":       {"max_size_mb": 2, "require_mraid": True,  "format": "html"},
    "google":     {"max_size_mb": 5, "require_mraid": True,  "format": "zip"},
    "tiktok":     {"max_size_mb": 2, "require_mraid": False, "format": "zip"},
    "applovin":   {"max_size_mb": 5, "require_mraid": False, "format": "html"},
    "unity_ads":  {"max_size_mb": 5, "require_mraid": False, "format": "html"},
    "ironsource":  {"max_size_mb": 5, "require_mraid": False, "format": "html"},
}

Check = tuple[str, bool, str]  # (criterion, passed, detail)


def check_tier1(build_path: str, network: str) -> list[Check]:
    """Return [(criterion, passed, detail), ...] for Tier 1 checks."""
    rules = NETWORK_RULES[network]
    root = Path(build_path)
    results: list[Check] = []

    # size
    total = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    total_mb = total / (1024 * 1024)
    max_mb = rules["max_size_mb"]
    results.append(("size", total_mb <= max_mb, f"{total_mb:.1f}MB / {max_mb}MB"))

    # index.html
    has_index = (root / "index.html").exists()
    results.append(("index_html", has_index, "found" if has_index else "missing"))

    # mraid (only when required)
    if rules["require_mraid"]:
        has_mraid = (root / "mraid.js").exists()
        results.append(("mraid", has_mraid, "found" if has_mraid else "missing mraid.js"))

    # asset count (informational — always passes)
    file_count = sum(1 for f in root.rglob("*") if f.is_file())
    results.append(("assets", True, f"{file_count} files"))

    return results


def format_results(checks: list[Check]) -> str:
    lines = [f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}" for name, passed, detail in checks]
    return "\n".join(lines)
