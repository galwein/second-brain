"""Browser bookmarks connector — reads Chromium-based bookmark files locally.

Supports Comet (personal) and Edge (work) with zero authentication.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from second_brain.models import Item, ItemMeta

logger = logging.getLogger("second-brain.connectors.bookmarks")

# Chromium epoch: microseconds since 1601-01-01
_CHROMIUM_EPOCH_OFFSET = 11644473600

BROWSER_PATHS = {
    "comet": Path.home() / "Library/Application Support/Comet/Default/Bookmarks",
    "edge": Path.home() / "Library/Application Support/Microsoft Edge/Default/Bookmarks",
}

BROWSER_STORE_MAP = {
    "comet": "personal",
    "edge": "work",
}


def _chromium_timestamp(ts_str: str) -> datetime:
    """Convert Chromium microsecond timestamp to datetime."""
    try:
        ts = int(ts_str)
        if ts > 0:
            epoch_seconds = (ts / 1_000_000) - _CHROMIUM_EPOCH_OFFSET
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        pass
    return datetime.now(tz=timezone.utc)


def _walk_bookmarks(node: dict) -> list[dict]:
    """Recursively extract bookmarks from a Chromium bookmark tree."""
    items = []
    if node.get("type") == "url":
        items.append({
            "name": node.get("name", ""),
            "url": node.get("url", ""),
            "date_added": node.get("date_added", "0"),
            "folder": node.get("_folder", ""),
        })
    for child in node.get("children", []):
        child["_folder"] = node.get("name", "")
        items.extend(_walk_bookmarks(child))
    return items


def read_browser_bookmarks(browser: str) -> list[dict]:
    """Read bookmarks from a specific browser."""
    path = BROWSER_PATHS.get(browser)
    if not path or not path.is_file():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read {browser} bookmarks: {e}")
        return []

    all_bookmarks = []
    for root_key in ("bookmark_bar", "other", "synced"):
        root = data.get("roots", {}).get(root_key, {})
        all_bookmarks.extend(_walk_bookmarks(root))

    return all_bookmarks


def bookmarks_to_items(browser: str) -> list[Item]:
    """Convert browser bookmarks to Second Brain Items."""
    store = BROWSER_STORE_MAP.get(browser, "personal")
    raw = read_browser_bookmarks(browser)
    items = []

    for bm in raw:
        url = bm["url"]
        name = bm["name"] or url
        added = _chromium_timestamp(bm["date_added"])
        folder = bm.get("folder", "")

        tags = ["bookmark", browser]
        if folder:
            tags.append(folder.lower().replace(" ", "-"))

        item = Item(
            meta=ItemMeta(
                title=name,
                source=f"{browser}-bookmarks",
                store=store,
                category="Inbox",
                tags=tags,
                created=added,
                updated=added,
                summary=url[:200],
            ),
            content=f"## {name}\n\n**URL:** {url}\n**Source:** {browser.title()} bookmark\n**Added:** {added.strftime('%Y-%m-%d')}\n**Folder:** {folder or 'Root'}",
        )
        items.append(item)

    return items
