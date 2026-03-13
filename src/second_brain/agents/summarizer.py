"""Summarization helpers for Copilot-native AI.

Instead of calling an external LLM, these helpers format item content
for Copilot to summarize directly.
"""
from second_brain.models import Item


def format_item_for_summary(item: Item) -> str:
    """Format a single item for Copilot to summarize."""
    lines = [
        "# Summarize This Item\n",
        f"**Title:** {item.meta.title}",
        f"**Source:** {item.meta.source}",
        f"**Store:** {item.meta.store}",
        f"**Category:** {item.meta.category}",
        f"**Tags:** {', '.join(item.meta.tags) if item.meta.tags else 'none'}",
        f"**Created:** {item.meta.created}",
        f"\n---\n\n{item.content}",
        "\n---\n",
        "Please provide:",
        "1. A concise executive summary (1-3 sentences)",
        "2. Key points as bullet points",
        "3. Any action items found",
        "4. Suggested keywords/tags",
    ]
    return "\n".join(lines)


def format_topic_for_summary(topic: str, items: list[Item]) -> str:
    """Format multiple items about a topic for Copilot to synthesize."""
    lines = [
        f"# Synthesize: {topic}\n",
        f"Found **{len(items)} items** related to \"{topic}\".\n",
        "---\n",
    ]

    for i, item in enumerate(items[:15], 1):
        lines.append(f"## Item {i}: {item.meta.title}")
        lines.append(f"*Source: {item.meta.source} | Tags: {', '.join(item.meta.tags)}*")
        lines.append(f"\n{item.content[:1000]}\n")
        lines.append("---\n")

    lines.extend([
        "Please provide:",
        "1. A comprehensive synthesis of what's known about this topic",
        "2. Key themes across the items",
        "3. Connections between items",
        "4. Gaps — what information might be missing",
    ])
    return "\n".join(lines)
