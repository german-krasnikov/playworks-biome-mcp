"""Batch DSL planner — converts intent to executable batch commands via Haiku."""
import re
from typing import Optional

_FENCE_RE = re.compile(r'^```\w*\s*$|^```\s*$', re.MULTILINE)


class PlanError(Exception):
    pass


def clean_dsl(raw: Optional[str], max_lines: int = 12) -> str:
    """Strip markdown fences, prose, blank lines. Return command-shaped lines only."""
    # Note: snake_case tool names expected. camelCase passes filter but fails dry_run validation.
    text = _FENCE_RE.sub("", raw or "").strip()
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        first_token = line.split()[0]
        if not first_token.replace("_", "").isalnum():
            continue
        out.append(line)
        if len(out) >= max_lines:
            break
    return "\n".join(out)


async def plan_batch(
    intent: str,
    kind: str,
    sampling,
    tool_registry: dict,
    ctx: str = "",
) -> str:
    """Returns batch DSL string or '' if disabled. May raise PlanError on failure."""
    if sampling is None or not sampling.enabled:
        return ""
    from .prompts import build_prompt
    from .whitelist import snapshot
    whitelist = snapshot(tool_registry)
    system = build_prompt(kind, whitelist)
    raw = await sampling.plan(intent, system, ctx)
    if not raw:
        return ""
    return clean_dsl(raw)
