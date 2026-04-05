"""Connection-finding context formatter.

Formats items so Copilot can identify connections between them.
No LLM calls — Copilot does the reasoning.
"""
from second_brain.models import Item


def format_connection_context(new_item: Item, existing_items: list[Item]) -> str:
    """Format a new item alongside existing items for Copilot to find connections."""
    lines = [
        "# Find Connections\n",
        "## New Item\n",
        f"**Title:** {new_item.meta.title}",
        f"**Source:** {new_item.meta.source}",
        f"**Tags:** {', '.join(new_item.meta.tags) if new_item.meta.tags else 'none'}",
        f"\n{new_item.content[:2000]}\n",
        "---\n",
        f"## Existing Items ({len(existing_items)} found)\n",
    ]

    for i, item in enumerate(existing_items[:15], 1):
        lines.append(f"### {i}. {item.meta.title}")
        lines.append(f"*Path: {item.path} | Tags: {', '.join(item.meta.tags)}*")
        lines.append(f"{item.content[:500]}\n")

    lines.extend([
        "---\n",
        "Please identify meaningful connections between the **new item** and existing items:",
        "- Shared topics or themes",
        "- Cause-and-effect relationships",
        "- Complementary information",
        "- Contradictions or conflicting viewpoints",
        "- Shared people, projects, or entities",
        "",
        "For each connection found, suggest whether items should be linked or tagged similarly.",
    ])
    return "\n".join(lines)
