"""CRUD MCP tool implementations for Second Brain."""
import logging
from datetime import datetime
from pathlib import Path

from second_brain.config import get_config
from second_brain.models import Item, ItemMeta, ParaCategory, SearchResult
from second_brain.storage.base import BaseStorage
from second_brain.storage.github_storage import GitHubStorage
from second_brain.storage.local_storage import LocalStorage

logger = logging.getLogger("second-brain.tools.crud")


def _get_stores() -> dict[str, BaseStorage]:
    """Initialize and return all configured stores."""
    config = get_config()
    stores: dict[str, BaseStorage] = {}
    for store_id, store_config in config.stores.items():
        if store_config.type == "github":
            stores[store_id] = GitHubStorage(store_id, store_config.path)
        else:
            stores[store_id] = LocalStorage(store_id, store_config.path)
    return stores


_stores_cache: dict[str, BaseStorage] | None = None


def get_stores() -> dict[str, BaseStorage]:
    global _stores_cache
    if _stores_cache is None:
        try:
            _stores_cache = _get_stores()
        except Exception as e:
            logger.error(f"Failed to initialize stores: {e}")
            _stores_cache = {}
    return _stores_cache


async def add_item(arguments: dict) -> str:
    """Add a new item to the Second Brain inbox."""
    stores = get_stores()
    store_id = arguments.get("store", "personal")
    title = arguments["title"]
    content = arguments["content"]
    tags = arguments.get("tags", [])

    if store_id not in stores:
        return f"❌ Unknown store: {store_id}. Available: {list(stores.keys())}"

    item = Item(
        meta=ItemMeta(
            title=title,
            source="manual",
            store=store_id,
            category="Inbox",
            tags=tags,
            created=datetime.now(),
            updated=datetime.now(),
        ),
        content=content,
    )

    path = await stores[store_id].write_item(item)
    return f"✅ Added to {store_id} store: {path}\n📁 Category: Inbox (use 'categorize' to get AI suggestions)"


async def get_item(arguments: dict) -> str:
    """Get a specific item by path."""
    stores = get_stores()
    store_id = arguments.get("store", "personal")
    path = arguments["path"]

    if store_id not in stores:
        return f"❌ Unknown store: {store_id}"

    try:
        item = await stores[store_id].read_item(path)
        lines = [
            f"# {item.meta.title}",
            f"**Store:** {item.meta.store} | **Category:** {item.meta.category}",
            f"**Tags:** {', '.join(item.meta.tags) if item.meta.tags else 'none'}",
            f"**Source:** {item.meta.source} | **Created:** {item.meta.created.strftime('%Y-%m-%d')}",
        ]
        if item.meta.summary:
            lines.append(f"**Summary:** {item.meta.summary}")
        lines.append(f"\n---\n\n{item.content}")
        return "\n".join(lines)
    except FileNotFoundError:
        return f"❌ Item not found: {path} in {store_id} store"


async def list_items(arguments: dict) -> str:
    """List items, optionally filtered by PARA category."""
    stores = get_stores()
    store_id = arguments.get("store", "all")
    category_name = arguments.get("category")

    category = ParaCategory(category_name) if category_name else None

    stores_to_list = (
        stores.items() if store_id == "all"
        else [(store_id, stores[store_id])]
    )

    all_items: list[tuple[str, Item]] = []
    for sid, storage in stores_to_list:
        try:
            items = await storage.list_items(category=category)
            all_items.extend((sid, item) for item in items)
        except Exception as e:
            logger.error(f"List failed in {sid}: {e}")

    if not all_items:
        cat_label = f" in {category_name}" if category_name else ""
        return f"📭 No items found{cat_label}."

    lines = [f"📋 **{len(all_items)} items** found:\n"]
    for sid, item in all_items:
        tags = f" [{', '.join(item.meta.tags)}]" if item.meta.tags else ""
        lines.append(f"- **{item.meta.title}** ({sid}:{item.path}){tags}")

    return "\n".join(lines)


async def move_item(arguments: dict) -> str:
    """Move an item to a new PARA location."""
    stores = get_stores()
    store_id = arguments.get("store", "personal")
    old_path = arguments["path"]
    new_path = arguments["new_path"]

    if store_id not in stores:
        return f"❌ Unknown store: {store_id}"

    try:
        result_path = await stores[store_id].move_item(old_path, new_path)
        return f"✅ Moved: {old_path} → {result_path}"
    except FileNotFoundError:
        return f"❌ Item not found: {old_path}"
    except Exception as e:
        return f"❌ Move failed: {e}"


async def search(arguments: dict) -> str:
    """Search across stores."""
    stores = get_stores()
    query = arguments["query"]
    store_id = arguments.get("store", "all")
    limit = arguments.get("limit", 10)

    stores_to_search = (
        stores.items() if store_id == "all"
        else [(store_id, stores[store_id])]
    )

    all_results: list[tuple[str, SearchResult]] = []
    for sid, storage in stores_to_search:
        try:
            results = await storage.search(query, limit=limit)
            all_results.extend((sid, r) for r in results)
        except Exception as e:
            logger.error(f"Search failed in {sid}: {e}")

    all_results.sort(key=lambda r: r[1].score, reverse=True)
    all_results = all_results[:limit]

    if not all_results:
        return f"🔍 No results found for: {query}"

    lines = [f"🔍 **{len(all_results)} results** for \"{query}\":\n"]
    for sid, result in all_results:
        item = result.item
        matched = f" (matched: {', '.join(result.matched_fields)})" if result.matched_fields else ""
        summary = item.meta.summary[:100] if item.meta.summary else item.content[:100].replace("\n", " ")
        lines.append(f"- **{item.meta.title}** ({sid}:{item.path}){matched}\n  {summary}...")

    return "\n".join(lines)
