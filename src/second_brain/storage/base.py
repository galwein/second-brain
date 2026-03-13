"""Abstract storage interface for Second Brain data stores."""
from abc import ABC, abstractmethod
from pathlib import Path

from second_brain.models import Item, ItemMeta, ParaCategory, SearchResult


class BaseStorage(ABC):
    """Abstract base class for Second Brain storage backends."""

    def __init__(self, store_id: str, root_path: Path):
        self.store_id = store_id
        self.root_path = root_path

    @abstractmethod
    async def read_item(self, path: str) -> Item:
        """Read an item by its relative path within the store."""
        ...

    @abstractmethod
    async def write_item(self, item: Item) -> str:
        """Write an item to the store. Returns the item's path."""
        ...

    @abstractmethod
    async def delete_item(self, path: str) -> bool:
        """Delete an item by path. Returns True if deleted."""
        ...

    @abstractmethod
    async def move_item(self, old_path: str, new_path: str) -> str:
        """Move an item from old_path to new_path. Returns new path."""
        ...

    @abstractmethod
    async def list_items(self, category: ParaCategory | None = None, tags: list[str] | None = None) -> list[Item]:
        """List items, optionally filtered by PARA category and/or tags."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Full-text search across items in this store."""
        ...

    def _category_path(self, category: ParaCategory) -> Path:
        """Get the filesystem path for a PARA category."""
        return self.root_path / category.value

    def _ensure_dirs(self):
        """Ensure all PARA category directories exist."""
        for cat in ParaCategory:
            (self.root_path / cat.value).mkdir(parents=True, exist_ok=True)
