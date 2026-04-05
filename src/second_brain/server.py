"""MCP server entry point for the Second Brain."""
import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger("second-brain")

# Create the MCP server instance
app = Server("second-brain")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Second Brain tools."""
    return [
        Tool(
            name="add_item",
            description="Add a new item to your Second Brain. Items land in the Inbox for later categorization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the item"},
                    "content": {"type": "string", "description": "Markdown content of the item"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work"],
                        "description": "Which store to save to (personal or work)",
                        "default": "personal",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for the item",
                        "default": [],
                    },
                },
                "required": ["title", "content"],
            },
        ),
        Tool(
            name="search",
            description="Search your Second Brain for items matching a query. Searches titles, content, and tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store to search (personal, work, or all)",
                        "default": "all",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_item",
            description="Get a specific item from your Second Brain by its path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the item (e.g., 'Inbox/my-note.md')"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work"],
                        "description": "Which store the item is in",
                        "default": "personal",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="list_items",
            description="List items in your Second Brain, optionally filtered by PARA category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Projects", "Areas", "Resources", "Archive", "Inbox"],
                        "description": "PARA category to list items from",
                    },
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store to list from",
                        "default": "all",
                    },
                },
            },
        ),
        Tool(
            name="move_item",
            description="Move an item to a different PARA category (e.g., from Inbox to Projects/my-project).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Current path of the item"},
                    "new_path": {"type": "string", "description": "New path for the item (e.g., 'Projects/my-project/note.md')"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work"],
                        "description": "Which store the item is in",
                        "default": "personal",
                    },
                },
                "required": ["path", "new_path"],
            },
        ),
        Tool(
            name="get_inbox",
            description="Show all items in the Inbox awaiting categorization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store's inbox to show",
                        "default": "all",
                    },
                },
            },
        ),
        Tool(
            name="categorize",
            description="Use AI to suggest a PARA category and tags for an item. Does not move the item automatically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the item to categorize"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work"],
                        "description": "Which store the item is in",
                        "default": "personal",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="summarize",
            description="Use AI to generate a summary of an item or a topic across your Second Brain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to a specific item to summarize (optional)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Topic to summarize across all items (optional, alternative to path)",
                    },
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store to use",
                        "default": "all",
                    },
                },
            },
        ),
        Tool(
            name="sync_teams",
            description="Sync recent messages and highlights from Microsoft Teams into your work Second Brain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back for messages",
                        "default": 7,
                    },
                },
            },
        ),
        Tool(
            name="review_sprint",
            description="Review work items for completeness and hygiene. Pass work items fetched from the ADO MCP. Checks for missing descriptions, repro steps, acceptance criteria, and stale items. Does NOT modify anything.",
            inputSchema={
                "type": "object",
                "properties": {
                    "work_items": {
                        "type": "array",
                        "description": "List of work item objects from the ADO MCP. Each should have: id, title, work_item_type (Bug/Task), state, priority, url, description, repro_steps, acceptance_criteria, changed_date",
                        "items": {"type": "object"},
                    },
                    "stale_days": {
                        "type": "integer",
                        "description": "Days without update to flag as stale",
                        "default": 14,
                    },
                },
                "required": ["work_items"],
            },
        ),
        Tool(
            name="sync_onedrive",
            description="Sync recent documents from your mounted OneDrive or SharePoint into the work store. Reads files directly from the filesystem — no auth needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back for changes",
                        "default": 7,
                    },
                    "subfolder": {
                        "type": "string",
                        "description": "Subfolder to scan, e.g. 'MSHealthIL - Documents' for SharePoint. Omit to scan all of OneDrive.",
                    },
                },
            },
        ),
        Tool(
            name="sync_ado",
            description="Sync ADO work items into your work Second Brain store. Pass work items fetched from the ADO MCP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "work_items": {
                        "type": "array",
                        "description": "List of work item objects from the ADO MCP. Each should have: id, title, work_item_type (Bug/Task), state, priority, url, description, area_path, iteration_path, tags",
                        "items": {"type": "object"},
                    },
                },
                "required": ["work_items"],
            },
        ),
        Tool(
            name="sync_bookmarks",
            description="Sync browser bookmarks from Comet (personal) and Edge (work) into your Second Brain. Reads local files — no auth needed.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="sync_calendar",
            description="Process and format calendar events from the Google Calendar MCP. Optionally saves events to your Second Brain. Pass events fetched by Copilot from the Google Calendar MCP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "description": "List of calendar event objects from the Google Calendar MCP. Each should have: summary, start, end, location, description, htmlLink, attendees, status",
                        "items": {"type": "object"},
                    },
                    "save": {
                        "type": "boolean",
                        "description": "Whether to save events to the Second Brain store (default: false — just format and display)",
                        "default": False,
                    },
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work"],
                        "description": "Which store to save to (only used when save=true)",
                        "default": "personal",
                    },
                },
                "required": ["events"],
            },
        ),
        Tool(
            name="find_connections",
            description="Find connections between an item and other items in your Second Brain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the item to find connections for"},
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store(s) to search for connections",
                        "default": "all",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="dashboard",
            description="Show a summary dashboard of your Second Brain — item counts, recent activity, inbox status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "enum": ["personal", "work", "all"],
                        "description": "Which store to show dashboard for",
                        "default": "all",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls with error handling."""
    try:
        from second_brain.tools.crud import add_item, get_item, list_items, move_item, search
        from second_brain.tools.para import get_inbox, categorize, summarize, find_connections, dashboard
        from second_brain.tools.sync import sync_teams, sync_onedrive, review_sprint, sync_ado, sync_bookmarks, sync_calendar

        handlers = {
            "add_item": add_item,
            "get_item": get_item,
            "list_items": list_items,
            "move_item": move_item,
            "search": search,
            "get_inbox": get_inbox,
            "categorize": categorize,
            "summarize": summarize,
            "find_connections": find_connections,
            "dashboard": dashboard,
            "sync_teams": sync_teams,
            "review_sprint": review_sprint,
            "sync_onedrive": sync_onedrive,
            "sync_ado": sync_ado,
            "sync_bookmarks": sync_bookmarks,
            "sync_calendar": sync_calendar,
        }

        handler = handlers.get(name)
        if handler:
            result = await handler(arguments)
            return [TextContent(type="text", text=result)]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except FileNotFoundError as e:
        logger.error(f"Tool '{name}' file not found: {e}")
        return [TextContent(type="text", text=f"❌ File not found: {e}")]
    except PermissionError as e:
        logger.error(f"Tool '{name}' permission denied: {e}")
        return [TextContent(type="text", text=f"❌ Permission denied: {e}")]
    except ValueError as e:
        logger.error(f"Tool '{name}' invalid input: {e}")
        return [TextContent(type="text", text=f"❌ Invalid input: {e}")]
    except Exception as e:
        logger.exception(f"Tool '{name}' failed")
        return [TextContent(type="text", text=f"❌ Error in '{name}': {type(e).__name__}: {e}")]


def main():
    """Start the Second Brain MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Second Brain MCP server...")

    # Validate config at startup
    try:
        from second_brain.config import get_config
        get_config()
        logger.info("Config loaded successfully.")
    except FileNotFoundError:
        logger.warning(
            "Config file not found at ~/.config/second-brain/config.yaml. "
            "Copy config.example.yaml and fill in your settings."
        )
    except Exception as e:
        logger.warning(f"Config issue (tools may not work): {e}")

    asyncio.run(_run())


async def _run():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    main()
