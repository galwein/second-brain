"""PARA-specific MCP tool implementations."""
import logging
from datetime import datetime

from second_brain.models import Item, ParaCategory
from second_brain.tools.crud import get_stores

logger = logging.getLogger("second-brain.tools.para")


async def get_inbox(arguments: dict) -> str:
    """Show all items in the Inbox awaiting categorization."""
    stores = get_stores()
    store_id = arguments.get("store", "all")

    stores_to_check = (
        stores.items() if store_id == "all"
        else [(store_id, stores[store_id])]
    )

    all_inbox: list[tuple[str, Item]] = []
    for sid, storage in stores_to_check:
        try:
            items = await storage.list_items(category=ParaCategory.INBOX)
            all_inbox.extend((sid, item) for item in items)
        except Exception as e:
            logger.error(f"Failed to check inbox in {sid}: {e}")

    if not all_inbox:
        return "📭 Inbox is empty! All items have been categorized."

    lines = [f"📬 **{len(all_inbox)} items in Inbox:**\n"]
    for sid, item in all_inbox:
        created = item.meta.created.strftime("%Y-%m-%d") if isinstance(item.meta.created, datetime) else str(item.meta.created)
        tags = f" [{', '.join(item.meta.tags)}]" if item.meta.tags else ""
        lines.append(f"- **{item.meta.title}** ({sid}:{item.path}) — {created}{tags}")

    lines.append(f"\n💡 Use 'categorize' to get AI suggestions for placement.")
    return "\n".join(lines)


async def categorize(arguments: dict) -> str:
    """Return item content + PARA guidelines for Copilot to categorize."""
    stores = get_stores()
    store_id = arguments.get("store", "personal")
    path = arguments["path"]

    if store_id not in stores:
        return f"❌ Unknown store: {store_id}"

    try:
        item = await stores[store_id].read_item(path)
    except FileNotFoundError:
        return f"❌ Item not found: {path}"

    # Gather existing category folders for context
    from second_brain.models import ParaCategory as PC
    existing = []
    for cat in [PC.PROJECTS, PC.AREAS, PC.RESOURCES]:
        cat_items = await stores[store_id].list_items(category=cat)
        folders = set()
        for ci in cat_items:
            parts = ci.path.split("/")
            if len(parts) >= 2:
                folders.add(f"{parts[0]}/{parts[1]}")
        existing.extend(sorted(folders))

    from second_brain.agents.categorizer import format_categorization_context
    return format_categorization_context(item, existing_categories=existing if existing else None)


async def summarize(arguments: dict) -> str:
    """Return item content for Copilot to summarize."""
    stores = get_stores()
    path = arguments.get("path")
    topic = arguments.get("topic")
    store_id = arguments.get("store", "all")

    if path:
        sid = store_id if store_id != "all" else "personal"
        if sid not in stores:
            return f"❌ Unknown store: {sid}"
        try:
            item = await stores[sid].read_item(path)
            from second_brain.agents.summarizer import format_item_for_summary
            return format_item_for_summary(item)
        except FileNotFoundError:
            return f"❌ Item not found: {path}"
    elif topic:
        all_items = []
        stores_to_search = stores.items() if store_id == "all" else [(store_id, stores[store_id])]
        for sid, storage in stores_to_search:
            results = await storage.search(topic, limit=10)
            all_items.extend(r.item for r in results)

        if not all_items:
            return f"🔍 No items found about '{topic}' to summarize."

        from second_brain.agents.summarizer import format_topic_for_summary
        return format_topic_for_summary(topic, all_items)
    else:
        return "Please provide either a 'path' to summarize a specific item, or a 'topic' to synthesize across items."


async def find_connections(arguments: dict) -> str:
    """Find connections between an item and existing items."""
    stores = get_stores()
    store_id = arguments.get("store", "all")
    path = arguments.get("path", "")

    if not path:
        return "Please provide a 'path' to the item you want to find connections for."

    # Determine which store the item is in
    sid = store_id if store_id != "all" else "personal"
    if sid not in stores:
        return f"❌ Unknown store: {sid}"

    try:
        item = await stores[sid].read_item(path)
    except FileNotFoundError:
        return f"❌ Item not found: {path}"

    # Search for related items using title keywords and tags
    search_terms = item.meta.title.split()[:5] + item.meta.tags[:3]
    query = " ".join(search_terms)

    related_items = []
    stores_to_search = stores.items() if store_id == "all" else [(store_id, stores[store_id])]
    for search_sid, storage in stores_to_search:
        results = await storage.search(query, limit=15)
        for r in results:
            # Don't include the item itself
            if r.item.path != path:
                related_items.append(r.item)

    if not related_items:
        return f"🔗 No potentially related items found for '{item.meta.title}'."

    from second_brain.agents.connector_agent import format_connection_context
    return format_connection_context(item, related_items)


async def dashboard(arguments: dict) -> str:
    """Show a summary dashboard of the Second Brain."""
    stores = get_stores()
    store_id = arguments.get("store", "all")

    stores_to_show = stores.items() if store_id == "all" else [(store_id, stores[store_id])]

    lines = ["🧠 **Second Brain Dashboard**\n"]

    for sid, storage in stores_to_show:
        lines.append(f"### 📦 {sid.title()} Store\n")
        total = 0
        for cat in ParaCategory:
            try:
                items = await storage.list_items(category=cat)
                count = len(items)
                total += count
                emoji = {"Projects": "🎯", "Areas": "🔄", "Resources": "📚", "Archive": "📦", "Inbox": "📬"}.get(cat.value, "📁")
                lines.append(f"  {emoji} **{cat.value}:** {count} items")
            except Exception:
                lines.append(f"  📁 **{cat.value}:** error reading")
        lines.append(f"  **Total:** {total} items\n")

    return "\n".join(lines)
