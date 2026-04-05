"""Sync/connector MCP tool implementations."""
import logging
from datetime import datetime

from second_brain.connectors.teams import TeamsConnector
from second_brain.connectors.onedrive import OneDriveConnector
from second_brain.tools.crud import get_stores

logger = logging.getLogger("second-brain.tools.sync")

# Cache connectors
_connectors: dict | None = None


def _get_connectors() -> dict:
    global _connectors
    if _connectors is None:
        _connectors = {
            "teams": TeamsConnector(),
            "onedrive": OneDriveConnector(),
        }
    return _connectors


async def sync_teams(arguments: dict) -> str:
    """Sync recent Teams messages into the work store."""
    stores = get_stores()
    connectors = _get_connectors()
    teams: TeamsConnector = connectors["teams"]
    days_back = arguments.get("days_back", 7)

    if "work" not in stores:
        return "❌ Work store not configured."

    # Authenticate if needed
    if not teams._client:
        lines = ["🔐 Authenticating with Microsoft Teams...\n"]
        success = await teams.authenticate()
        if not success:
            return "❌ Teams authentication failed. Check your Microsoft config (client_id, tenant_id)."
        lines.append("✅ Authenticated!\n")
    else:
        lines = []

    lines.append(f"🔄 Syncing Teams messages from the last {days_back} days...\n")
    result = await teams.sync(stores["work"], days_back=days_back)
    lines.append(result.summary())
    return "\n".join(lines)


async def sync_onedrive(arguments: dict) -> str:
    """Sync recent OneDrive/SharePoint documents into the work store."""
    stores = get_stores()
    connectors = _get_connectors()
    onedrive: OneDriveConnector = connectors["onedrive"]
    days_back = arguments.get("days_back", 7)
    subfolder = arguments.get("subfolder", None)

    if "work" not in stores:
        return "❌ Work store not configured."

    # Check mount
    mounted = await onedrive.authenticate()
    if not mounted:
        return "❌ OneDrive is not mounted. Open the OneDrive app and sign in."

    label = f"'{subfolder}'" if subfolder else "OneDrive"
    lines = [f"🔄 Scanning {label} for files modified in the last {days_back} days...\n"]

    try:
        items = await onedrive.fetch_new_items(days_back=days_back, subfolder=subfolder)
    except Exception as exc:
        return f"❌ Failed to scan OneDrive: {exc}"

    if not items:
        lines.append("📭 No recently modified supported files found.")
        return "\n".join(lines)

    store = stores["work"]
    count = 0
    for item in items:
        try:
            await store.write_item(item)
            count += 1
        except Exception as exc:
            logger.warning(f"Failed to write {item.meta.title}: {exc}")

    lines.append(f"✅ Synced {count} files into work store.")
    lines.append(f"Supported formats: {', '.join(sorted(onedrive.SUPPORTED_EXTENSIONS))}")
    return "\n".join(lines)


async def sync_bookmarks(arguments: dict) -> str:
    """Sync browser bookmarks into the Second Brain stores."""
    from second_brain.connectors.bookmarks import bookmarks_to_items, BROWSER_PATHS, BROWSER_STORE_MAP

    stores = get_stores()
    lines = []
    total = 0

    for browser in ("comet", "edge"):
        target_store = BROWSER_STORE_MAP.get(browser, "personal")
        if target_store not in stores:
            lines.append(f"⚠️ {browser.title()}: {target_store} store not configured, skipping.")
            continue

        items = bookmarks_to_items(browser)
        if not items:
            path = BROWSER_PATHS.get(browser, "?")
            lines.append(f"📭 {browser.title()}: no bookmarks found (checked {path})")
            continue

        store = stores[target_store]
        count = 0
        for item in items:
            try:
                await store.write_item(item)
                count += 1
            except Exception as exc:
                logger.warning(f"Failed to write bookmark {item.meta.title}: {exc}")

        lines.append(f"✅ {browser.title()}: synced {count} bookmarks → {target_store} store")
        total += count

    if total == 0:
        lines.append("\nNo new bookmarks found across browsers.")
    else:
        lines.append(f"\n📚 Total: {total} bookmarks synced.")

    return "\n".join(lines)


async def sync_calendar(arguments: dict) -> str:
    """Process calendar events from the Google Calendar MCP.

    Accepts a list of event objects (fetched by Copilot from the Google Calendar
    MCP) and returns a nicely formatted summary.  Optionally saves events to
    the personal Second Brain store when ``save`` is True.
    """
    events = arguments.get("events", [])
    save = arguments.get("save", False)
    store_name = arguments.get("store", "personal")

    if not events:
        return (
            "📭 No calendar events provided.\n\n"
            "**How to use:** First ask Copilot to fetch events from the Google Calendar MCP, "
            "then pass them to this tool via the `events` parameter."
        )

    lines: list[str] = []
    saved = 0

    for ev in events:
        summary = ev.get("summary", "(no title)")
        start_raw = ev.get("start", {})
        end_raw = ev.get("end", {})
        location = ev.get("location", "")
        description = ev.get("description", "")
        html_link = ev.get("htmlLink", "")
        status = ev.get("status", "")
        attendees = ev.get("attendees", [])

        # Parse start/end — handles both dateTime and date (all-day)
        start_str = start_raw if isinstance(start_raw, str) else start_raw.get("dateTime", start_raw.get("date", "?"))
        end_str = end_raw if isinstance(end_raw, str) else end_raw.get("dateTime", end_raw.get("date", "?"))

        # Format for display
        line = f"📅 **{summary}**\n"
        line += f"   🕐 {start_str} → {end_str}\n"
        if location:
            line += f"   📍 {location}\n"
        if attendees:
            names = [a.get("email", a.get("displayName", "?")) for a in attendees[:5]]
            if len(attendees) > 5:
                names.append(f"+{len(attendees) - 5} more")
            line += f"   👥 {', '.join(names)}\n"
        if status and status != "confirmed":
            line += f"   ⚠️ Status: {status}\n"
        if html_link:
            line += f"   🔗 {html_link}\n"
        lines.append(line)

        # Optionally save to brain
        if save:
            from second_brain.models import Item, ItemMeta

            stores = get_stores()
            if store_name not in stores:
                lines.append(f"   ⚠️ Cannot save — {store_name} store not configured")
                continue

            tags = ["calendar"]
            if location:
                tags.append("has-location")
            if attendees:
                tags.append("meeting")

            content = f"## {summary}\n\n"
            content += f"**When:** {start_str} → {end_str}\n"
            if location:
                content += f"**Where:** {location}\n"
            if attendees:
                content += f"**Attendees:** {', '.join(a.get('email', '?') for a in attendees)}\n"
            if description:
                content += f"\n{description}\n"
            if html_link:
                content += f"\n[Open in Google Calendar]({html_link})\n"

            item = Item(
                meta=ItemMeta(
                    title=summary,
                    source="google-calendar",
                    store=store_name,
                    category="Inbox",
                    tags=tags,
                    created=datetime.now(),
                    updated=datetime.now(),
                    summary=f"Calendar: {summary} ({start_str})",
                ),
                content=content,
            )

            try:
                await stores[store_name].write_item(item)
                saved += 1
            except Exception as exc:
                logger.warning(f"Failed to save event '{summary}': {exc}")

    header = f"🗓️ **{len(events)} Calendar Event(s):**\n"
    result = header + "\n".join(lines)

    if save and saved:
        result += f"\n\n💾 Saved {saved} event(s) to {store_name} store."

    return result


async def review_sprint(arguments: dict) -> str:
    """Review work items for completeness and hygiene.

    Expects `work_items` — a list of dicts with fields like id, title,
    work_item_type, state, priority, description, repro_steps, etc.
    Copilot fetches these from the ADO MCP and passes them in.
    """
    work_items = arguments.get("work_items", [])
    stale_days = arguments.get("stale_days", 14)

    if not work_items:
        return (
            "📭 No work items provided.\n\n"
            "**How to use:** First ask Copilot to fetch your work items from the ADO MCP, "
            "then pass them to this tool via the `work_items` parameter."
        )

    from second_brain.connectors.ado import review_work_items

    try:
        report = review_work_items(work_items, stale_threshold_days=stale_days)
        return report.format()
    except Exception as exc:
        return f"❌ Failed to review sprint: {exc}"


async def sync_ado(arguments: dict) -> str:
    """Sync ADO work items into the work store.

    Expects `work_items` — a list of dicts with fields like id, title,
    work_item_type, state, priority, description, area_path, iteration_path,
    tags, etc.  Copilot fetches these from the ADO MCP and passes them in.
    """
    work_items = arguments.get("work_items", [])

    if not work_items:
        return (
            "📭 No work items provided.\n\n"
            "**How to use:** First ask Copilot to fetch your work items from the ADO MCP, "
            "then pass them to this tool via the `work_items` parameter."
        )

    from second_brain.connectors.ado import strip_html
    from second_brain.models import Item, ItemMeta

    stores = get_stores()
    if "work" not in stores:
        return "❌ Work store not configured."

    store = stores["work"]
    count = 0

    for item in work_items:
        wi_id = item.get("id", 0)
        title = item.get("title", "")
        item_type = item.get("work_item_type", item.get("type", ""))
        state = item.get("state", "")
        priority = item.get("priority", 0)
        if isinstance(priority, str):
            try:
                priority = int(priority)
            except ValueError:
                priority = 0
        description = strip_html(item.get("description", "") or "")
        url = item.get("url", "")
        area = item.get("area_path", "").split("\\")[-1] if item.get("area_path") else ""
        iteration = item.get("iteration_path", "").split("\\")[-1] if item.get("iteration_path") else ""
        tags_str = item.get("tags", "") or ""

        if "placeholder" in title.lower():
            continue

        if item_type == "Bug":
            category = "Projects/bugs"
        elif state == "Active":
            category = "Projects/active-tasks"
        else:
            category = "Projects/backlog"

        priority_label = {1: "🔴 P1", 2: "🟡 P2", 3: "🟢 P3", 4: "⚪ P4"}.get(priority, "")
        state_emoji = {"New": "🆕", "Active": "🔵", "Blocked": "🔴"}.get(state, "⚪")
        tags = [tag.strip().lower().replace(" ", "-") for tag in tags_str.split(";") if tag.strip()]
        if item_type:
            tags.append(item_type.lower())
        if priority:
            tags.append(f"p{priority}")

        content = f"""## {title}

**ADO ID:** [{wi_id}]({url})
**Type:** {item_type} | **State:** {state_emoji} {state} | **Priority:** {priority_label}
**Sprint:** {iteration} | **Area:** {area}

{description}
"""

        item_record = Item(
            meta=ItemMeta(
                title=title,
                source="ado",
                store="work",
                category=category,
                tags=tags,
                created=datetime.now(),
                updated=datetime.now(),
                summary=f"ADO #{wi_id} - {item_type} ({state}) - {priority_label}",
            ),
            content=content,
        )

        await store.write_item(item_record)
        count += 1

    return f"✅ Synced {count} work items from ADO into work store."
