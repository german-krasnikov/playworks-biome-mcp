"""Match intent text to catalog entries."""
import re

from .catalog import FlagCatalog, FlagEntry


class FlagRecommender:
    def __init__(self, catalog: FlagCatalog):
        self._catalog = catalog

    def recommend(self, intent: str, max_results: int = 5) -> list[FlagEntry]:
        if not intent:
            return []
        keywords = [w.lower() for w in re.findall(r"\b\w{3,}\b", intent)]
        return self._catalog.find_by_intent(keywords)[:max_results]
