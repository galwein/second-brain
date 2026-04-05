"""GitHub-backed storage implementation.

Stores notes as Markdown files with YAML frontmatter in a local git
clone.  Uses python-frontmatter for serialization and subprocess for
git operations (add / commit / push / pull).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import frontmatter

from second_brain.models import Item, ItemMeta, ParaCategory, SearchResult
from second_brain.storage.base import BaseStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(title: str) -> str:
    """Convert *title* to a filesystem-safe slug (lowercase, hyphens)."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def _item_to_frontmatter(item: Item) -> str:
    """Serialize an *Item* to a Markdown string with YAML frontmatter."""
    metadata = {
        "title": item.meta.title,
        "source": item.meta.source,
        "store": item.meta.store,
        "category": item.meta.category,
        "tags": item.meta.tags,
        "created": item.meta.created.isoformat(),
        "updated": item.meta.updated.isoformat(),
        "summary": item.meta.summary,
    }
    post = frontmatter.Post(item.content, **metadata)
    return frontmatter.dumps(post)


def _frontmatter_to_item(rel_path: str, raw: str) -> Item:
    """Parse a Markdown string with YAML frontmatter into an *Item*."""
    post = frontmatter.loads(raw)
    meta = ItemMeta(
        title=post.get("title", ""),
        source=post.get("source", "manual"),
        store=post.get("store", "personal"),
        category=post.get("category", "Inbox"),
        tags=post.get("tags", []),
        created=_parse_dt(post.get("created")),
        updated=_parse_dt(post.get("updated")),
        summary=post.get("summary", ""),
    )
    return Item(meta=meta, content=post.content, path=rel_path)


def _parse_dt(value: str | datetime | None) -> datetime:
    """Best-effort parse of a datetime value coming from frontmatter."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()


# ---------------------------------------------------------------------------
# GitHubStorage
# ---------------------------------------------------------------------------

class GitHubStorage(BaseStorage):
    """Storage backed by a local git clone of a GitHub repository."""

    def __init__(self, store_id: str, root_path: Path):
        super().__init__(store_id, root_path)
        self._ensure_dirs()

    # -- git helpers --------------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root_path,
            capture_output=True,
            text=True,
            check=True,
        )

    def _git_commit(self, message: str, paths: list[str] | None = None) -> None:
        """Stage *paths* (or everything) and commit."""
        if paths:
            for p in paths:
                self._git("add", p)
        else:
            self._git("add", "-A")
        # Only commit when there are staged changes.
        status = self._git("status", "--porcelain")
        if status.stdout.strip():
            self._git("commit", "-m", message)

    # -- BaseStorage implementation -----------------------------------------

    async def read_item(self, path: str) -> Item:
        full = self.root_path / path
        if not full.is_file():
            raise FileNotFoundError(f"Item not found: {path}")
        raw = full.read_text(encoding="utf-8")
        return _frontmatter_to_item(path, raw)

    async def write_item(self, item: Item) -> str:
        # Generate a path when one isn't set yet.
        if not item.path:
            cat = item.meta.category or "Inbox"
            slug = _slugify(item.meta.title)
            item.path = f"{cat}/{slug}.md"

        item.meta.updated = datetime.now()

        full = self.root_path / item.path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(_item_to_frontmatter(item), encoding="utf-8")

        self._git_commit(f"Update {item.path}", [item.path])
        return item.path

    async def delete_item(self, path: str) -> bool:
        full = self.root_path / path
        if not full.is_file():
            return False
        full.unlink()
        self._git_commit(f"Delete {path}", [path])
        return True

    async def move_item(self, old_path: str, new_path: str) -> str:
        src = self.root_path / old_path
        dst = self.root_path / new_path
        if not src.is_file():
            raise FileNotFoundError(f"Source not found: {old_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        self._git("add", old_path)
        self._git("add", new_path)
        self._git_commit(f"Move {old_path} → {new_path}")
        return new_path

    async def list_items(
        self,
        category: ParaCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[Item]:
        search_root = (
            self._category_path(category) if category else self.root_path
        )
        items: list[Item] = []
        for md in sorted(search_root.rglob("*.md")):
            # Skip hidden dirs (e.g. .git)
            if any(part.startswith(".") for part in md.relative_to(self.root_path).parts):
                continue
            rel = str(md.relative_to(self.root_path))
            try:
                item = _frontmatter_to_item(rel, md.read_text(encoding="utf-8"))
            except Exception:
                continue
            if tags and not set(tags) & set(item.meta.tags):
                continue
            items.append(item)
        return items

    async def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        query_lower = query.lower()
        tokens = query_lower.split()
        results: list[SearchResult] = []

        for md in self.root_path.rglob("*.md"):
            if any(part.startswith(".") for part in md.relative_to(self.root_path).parts):
                continue
            rel = str(md.relative_to(self.root_path))
            try:
                item = _frontmatter_to_item(rel, md.read_text(encoding="utf-8"))
            except Exception:
                continue

            score = 0.0
            matched: list[str] = []

            title_lower = item.meta.title.lower()
            content_lower = item.content.lower()
            tags_lower = " ".join(item.meta.tags).lower()

            for tok in tokens:
                if tok in title_lower:
                    score += 3.0
                    if "title" not in matched:
                        matched.append("title")
                if tok in content_lower:
                    score += 1.0
                    if "content" not in matched:
                        matched.append("content")
                if tok in tags_lower:
                    score += 2.0
                    if "tags" not in matched:
                        matched.append("tags")

            if score > 0:
                results.append(SearchResult(item=item, score=score, matched_fields=matched))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
