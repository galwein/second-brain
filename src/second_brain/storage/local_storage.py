"""Local filesystem storage implementation.

Persists notes as Markdown files with YAML front-matter on the local
disk, suitable for development and offline use.  No git operations —
this is purely local.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import frontmatter

from second_brain.models import Item, ItemMeta, ParaCategory, SearchResult
from second_brain.storage.base import BaseStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(title: str) -> str:
    """Turn a human title into a filename-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _item_to_frontmatter(item: Item) -> str:
    """Serialise an *Item* to a Markdown string with YAML front-matter."""
    metadata: dict = {
        "title": item.meta.title,
        "source": item.meta.source,
        "store": item.meta.store,
        "category": item.meta.category,
        "tags": item.meta.tags,
        "created": item.meta.created.isoformat(),
        "updated": item.meta.updated.isoformat(),
    }
    if item.meta.summary:
        metadata["summary"] = item.meta.summary
    if item.meta.related:
        metadata["related"] = item.meta.related

    post = frontmatter.Post(item.content, **metadata)
    return frontmatter.dumps(post)


def _frontmatter_to_item(rel_path: str, raw: str) -> Item:
    """Parse a raw Markdown string with front-matter into an *Item*."""
    post = frontmatter.loads(raw)
    meta_dict = dict(post.metadata)

    # Parse datetimes — accept both str and datetime objects
    for key in ("created", "updated"):
        val = meta_dict.get(key)
        if isinstance(val, str):
            meta_dict[key] = datetime.fromisoformat(val)
        elif not isinstance(val, datetime):
            meta_dict[key] = datetime.now()

    # Ensure tags is a list
    if not isinstance(meta_dict.get("tags"), list):
        meta_dict["tags"] = []

    # Ensure related is a list
    if not isinstance(meta_dict.get("related"), list):
        meta_dict["related"] = []

    meta = ItemMeta(
        title=meta_dict.get("title", Path(rel_path).stem),
        source=meta_dict.get("source", "manual"),
        store=meta_dict.get("store", "personal"),
        category=meta_dict.get("category", "Inbox"),
        tags=meta_dict["tags"],
        created=meta_dict["created"],
        updated=meta_dict["updated"],
        summary=meta_dict.get("summary", ""),
        related=meta_dict["related"],
    )
    return Item(meta=meta, content=post.content, path=rel_path)


# ---------------------------------------------------------------------------
# LocalStorage
# ---------------------------------------------------------------------------

class LocalStorage(BaseStorage):
    """Store items as Markdown files on the local filesystem."""

    def __init__(self, store_id: str, root_path: Path):
        super().__init__(store_id, root_path)
        self._ensure_dirs()

    # -- abstract method implementations ------------------------------------

    async def read_item(self, path: str) -> Item:
        full = self.root_path / path
        if not full.is_file():
            raise FileNotFoundError(f"Item not found: {path}")
        raw = full.read_text(encoding="utf-8")
        return _frontmatter_to_item(path, raw)

    async def write_item(self, item: Item) -> str:
        if not item.path:
            cat = item.meta.category or "Inbox"
            slug = _slugify(item.meta.title) or "untitled"
            item.path = f"{cat}/{slug}.md"

        full = self.root_path / item.path
        full.parent.mkdir(parents=True, exist_ok=True)

        item.meta.updated = datetime.now()
        full.write_text(_item_to_frontmatter(item), encoding="utf-8")
        return item.path

    async def delete_item(self, path: str) -> bool:
        full = self.root_path / path
        if full.is_file():
            full.unlink()
            return True
        return False

    async def move_item(self, old_path: str, new_path: str) -> str:
        src = self.root_path / old_path
        dst = self.root_path / new_path
        if not src.is_file():
            raise FileNotFoundError(f"Source item not found: {old_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return new_path

    async def list_items(
        self,
        category: ParaCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[Item]:
        search_root = (
            self._category_path(category) if category else self.root_path
        )
        if not search_root.exists():
            return []

        items: list[Item] = []
        for md_file in search_root.rglob("*.md"):
            rel = str(md_file.relative_to(self.root_path))
            try:
                raw = md_file.read_text(encoding="utf-8")
                item = _frontmatter_to_item(rel, raw)
            except Exception:
                continue

            if tags and not set(tags) & set(item.meta.tags):
                continue
            items.append(item)

        return items

    async def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        terms = query.lower().split()
        if not terms:
            return []

        results: list[SearchResult] = []
        for md_file in self.root_path.rglob("*.md"):
            rel = str(md_file.relative_to(self.root_path))
            try:
                raw = md_file.read_text(encoding="utf-8")
                item = _frontmatter_to_item(rel, raw)
            except Exception:
                continue

            score = 0.0
            matched: list[str] = []
            title_lower = item.meta.title.lower()
            content_lower = item.content.lower()
            tags_lower = " ".join(item.meta.tags).lower()

            for term in terms:
                if term in title_lower:
                    score += 3.0
                    if "title" not in matched:
                        matched.append("title")
                if term in content_lower:
                    score += 1.0
                    if "content" not in matched:
                        matched.append("content")
                if term in tags_lower:
                    score += 2.0
                    if "tags" not in matched:
                        matched.append("tags")

            if score > 0:
                results.append(SearchResult(item=item, score=score, matched_fields=matched))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
