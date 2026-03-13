"""Unified search engine across Second Brain stores."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import get_config
from second_brain.models import SearchResult, StoreType
from second_brain.storage.base import BaseStorage
from second_brain.storage.github_storage import GitHubStorage
from second_brain.storage.local_storage import LocalStorage

logger = logging.getLogger("second-brain.search")


@dataclass
class UnifiedSearchResult:
    """Search result that includes store information."""
    result: SearchResult
    store: str  # "personal" or "work"


class SearchEngine:
    """Unified search across all Second Brain stores."""

    def __init__(self):
        config = get_config()
        self._stores: dict[str, BaseStorage] = {}

        for store_id, store_config in config.stores.items():
            if store_config.type == "github":
                self._stores[store_id] = GitHubStorage(store_id, store_config.path)
            else:
                self._stores[store_id] = LocalStorage(store_id, store_config.path)

    def get_store(self, store_id: str) -> BaseStorage:
        """Get a specific store by ID."""
        if store_id not in self._stores:
            raise ValueError(f"Unknown store: {store_id}. Available: {list(self._stores.keys())}")
        return self._stores[store_id]

    @property
    def stores(self) -> dict[str, BaseStorage]:
        return self._stores

    async def search(
        self,
        query: str,
        store: str = "all",
        limit: int = 20,
    ) -> list[UnifiedSearchResult]:
        """Search across stores.

        Args:
            query: Search query string.
            store: "personal", "work", or "all".
            limit: Max results.

        Returns:
            List of UnifiedSearchResult sorted by score.
        """
        results: list[UnifiedSearchResult] = []

        stores_to_search = (
            self._stores.items()
            if store == "all"
            else [(store, self._stores[store])]
        )

        for store_id, storage in stores_to_search:
            try:
                store_results = await storage.search(query, limit=limit)
                for sr in store_results:
                    results.append(UnifiedSearchResult(result=sr, store=store_id))
            except Exception as e:
                logger.error(f"Search failed in {store_id} store: {e}")

        # Sort by score descending, take top N
        results.sort(key=lambda r: r.result.score, reverse=True)
        return results[:limit]
