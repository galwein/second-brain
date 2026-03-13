"""Abstract connector interface for Second Brain data sources."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from second_brain.models import Item


@dataclass
class SyncResult:
    """Result of a connector sync operation."""
    connector_name: str
    target_store: str  # "personal" or "work"
    items_fetched: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        status = "✅" if self.success else "⚠️"
        lines = [
            f"{status} {self.connector_name} sync to {self.target_store} store",
            f"  Fetched: {self.items_fetched}, New: {self.items_new}, Updated: {self.items_updated}, Skipped: {self.items_skipped}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for err in self.errors[:3]:
                lines.append(f"    - {err}")
        return "\n".join(lines)


class BaseConnector(ABC):
    """Abstract base class for Second Brain connectors (data sources)."""

    def __init__(self, name: str, target_store: str):
        """
        Args:
            name: Human-readable connector name (e.g., "Teams", "OneDrive")
            target_store: Which store this connector writes to ("personal" or "work")
        """
        self.name = name
        self.target_store = target_store

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the data source. Returns True if successful."""
        ...

    @abstractmethod
    async def fetch_new_items(self, days_back: int = 7) -> list[Item]:
        """Fetch new/updated items from the data source.
        
        Args:
            days_back: How many days to look back for new items.
            
        Returns:
            List of Items ready to be ingested into the store.
        """
        ...

    @abstractmethod
    async def get_status(self) -> dict:
        """Get the current status of the connector (authenticated, last sync, etc.)."""
        ...

    async def sync(self, storage, days_back: int = 7) -> SyncResult:
        """Full sync: fetch items and write them to storage.
        
        Args:
            storage: A BaseStorage instance to write items to.
            days_back: How many days to look back.
            
        Returns:
            SyncResult with details about what was synced.
        """
        result = SyncResult(connector_name=self.name, target_store=self.target_store)
        
        try:
            items = await self.fetch_new_items(days_back=days_back)
            result.items_fetched = len(items)
            
            for item in items:
                try:
                    # Check if item already exists (by title/source match)
                    existing = await storage.search(item.meta.title, limit=1)
                    if existing and existing[0].item.meta.source == item.meta.source:
                        result.items_skipped += 1
                        continue
                    
                    await storage.write_item(item)
                    result.items_new += 1
                except Exception as e:
                    result.errors.append(f"Failed to write '{item.meta.title}': {e}")
        except Exception as e:
            result.errors.append(f"Fetch failed: {e}")
        
        result.completed_at = datetime.now()
        return result
