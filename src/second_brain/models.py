"""Data models for the Second Brain."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ParaCategory(Enum):
    PROJECTS = "Projects"
    AREAS = "Areas"
    RESOURCES = "Resources"
    ARCHIVE = "Archive"
    INBOX = "Inbox"


class StoreType(Enum):
    PERSONAL = "personal"
    WORK = "work"


@dataclass
class ItemMeta:
    """Metadata for a Second Brain item (stored as YAML frontmatter)."""
    title: str
    source: str = "manual"  # manual, telegram, teams, onedrive, etc.
    store: str = "personal"  # personal or work
    category: str = "Inbox"  # PARA category path, e.g., "Projects/my-project"
    tags: list[str] = field(default_factory=list)
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    summary: str = ""
    related: list[str] = field(default_factory=list)  # paths to related items


@dataclass
class Item:
    """A Second Brain item — a piece of knowledge."""
    meta: ItemMeta
    content: str  # Markdown content (without frontmatter)
    path: str = ""  # Relative path within the store, e.g., "Inbox/my-note.md"

    @property
    def filename(self) -> str:
        return Path(self.path).name if self.path else ""

    @property
    def para_category(self) -> ParaCategory:
        top = self.path.split("/")[0] if self.path else "Inbox"
        try:
            return ParaCategory(top)
        except ValueError:
            return ParaCategory.INBOX


@dataclass
class SearchResult:
    """A search result with relevance info."""
    item: Item
    score: float = 0.0
    matched_fields: list[str] = field(default_factory=list)  # e.g., ["title", "content", "tags"]
