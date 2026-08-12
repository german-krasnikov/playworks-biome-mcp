"""F12 Compliance Checker MCP tool."""
from __future__ import annotations

from ..compliance.checker import NETWORK_RULES, check_tier1, format_results
from ..tools import maybe_expose


async def check_compliance(build_path: str, network: str, screenshot_path: str = "") -> str:
    """Check build against ad network requirements. Returns PASS/FAIL per criterion."""
    if network not in NETWORK_RULES:
        known = ", ".join(sorted(NETWORK_RULES))
        return f"error: unknown network '{network}'. Known: {known}"

    checks = check_tier1(build_path, network)
    header = f"network={network}"

    # Tier 2: screenshot visual check (if provided)
    if screenshot_path:
        try:
            from ..sampling import SamplingService
            svc = SamplingService()
            prompt = "Check this playable ad: CTA button visible? Tutorial hint present? Works in both orientations?"
            desc = await svc.describe_image(prompt, screenshot_path)
            header += f"\nvisual: {desc}"
        except Exception as e:
            header += f"\nvisual: skipped ({e})"

    return f"{header}\n{format_results(checks)}"


def register_compliance_tools(mcp, exposed: set[str]) -> dict:
    maybe_expose(mcp, check_compliance, exposed, name="check_compliance", read_only=True)
    return {"check_compliance": (check_compliance, None)}
