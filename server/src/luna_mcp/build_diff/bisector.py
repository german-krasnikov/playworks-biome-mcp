"""Binary search to find regression culprit in log(N) probes."""
from __future__ import annotations

from typing import Awaitable, Callable


class Bisector:
    """Find first bad label between a known-good and known-bad."""

    def __init__(self, probe_fn: Callable[[str], Awaitable[bool]]):
        """probe_fn(label) → True if good, False if bad."""
        self._probe = probe_fn

    async def find_culprit(
        self, good_label: str, bad_label: str, intermediates: list[str]
    ) -> tuple[str, int]:
        """Returns (culprit_label, n_probes).
        intermediates = labels in chronological order between good and bad.
        """
        if not intermediates:
            return (bad_label, 0)
        ordered = [good_label] + intermediates + [bad_label]
        lo, hi = 0, len(ordered) - 1
        n_probes = 0
        while hi - lo > 1:
            mid = (lo + hi) // 2
            n_probes += 1
            try:
                is_good = await self._probe(ordered[mid])
            except Exception:
                is_good = False  # treat unknown as bad
            if is_good:
                lo = mid
            else:
                hi = mid
        return (ordered[hi], n_probes)
