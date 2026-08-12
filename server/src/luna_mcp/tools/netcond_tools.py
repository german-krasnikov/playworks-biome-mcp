"""S4.5 Network condition tools — throttle, block URLs, reset."""
from ..cdp_domains import NETWORK_PRESETS
from . import maybe_expose

_VALID_PROFILES = "|".join(sorted(NETWORK_PRESETS.keys()))


def register_netcond_tools(mcp, get_bridge, ensure_connected, *, exposed: set = frozenset()):
    async def set_network(profile: str = "offline") -> str:
        """Emulate network conditions. profile: online|offline|slow|3g|4g."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        if profile not in NETWORK_PRESETS:
            return f"[INVALID: {_VALID_PROFILES}]"
        try:
            await ensure_connected()
            await bridge.send_cdp("Network.enable")
            p = NETWORK_PRESETS[profile]
            await bridge.send_cdp("Network.emulateNetworkConditions", {
                "offline": p["offline"],
                "latency": p["latency"],
                "downloadThroughput": p["download"],
                "uploadThroughput": p["upload"],
            })
            return f"OK network={profile} (clear_network to reset)"
        except Exception as e:
            return f"[DEGRADED] {e}"

    maybe_expose(mcp, set_network, exposed, read_only=False)

    async def block_urls(patterns_csv: str = "") -> str:
        """Block URL patterns. patterns_csv: comma-separated globs."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        try:
            await ensure_connected()
            await bridge.send_cdp("Network.enable")
            urls = [p.strip() for p in patterns_csv.split(",") if p.strip()]
            await bridge.send_cdp("Network.setBlockedURLs", {"urls": urls})
            return f"OK blocked {len(urls)} patterns (clear_network to reset)"
        except Exception as e:
            return f"[DEGRADED] {e}"

    maybe_expose(mcp, block_urls, exposed, read_only=False)

    async def clear_network() -> str:
        """Reset network conditions and URL blocking."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        try:
            await ensure_connected()
            await bridge.send_cdp("Network.enable")
            p = NETWORK_PRESETS["online"]
            await bridge.send_cdp("Network.emulateNetworkConditions", {
                "offline": p["offline"],
                "latency": p["latency"],
                "downloadThroughput": p["download"],
                "uploadThroughput": p["upload"],
            })
            await bridge.send_cdp("Network.setBlockedURLs", {"urls": []})
            return "OK network reset"
        except Exception as e:
            return f"[DEGRADED] {e}"

    maybe_expose(mcp, clear_network, exposed, read_only=False)

    return {
        "set_network": (set_network, None),
        "block_urls": (block_urls, None),
        "clear_network": (clear_network, None),
    }
