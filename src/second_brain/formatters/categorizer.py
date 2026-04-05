"""PARA categorization context formatter.

Formats item content and PARA methodology rules as rich context for
Copilot to reason over. No LLM calls — Copilot does the reasoning.
"""
from second_brain.models import Item, ParaCategory
from second_brain.para_framework import PARA_GUIDELINES


def format_categorization_context(item: Item, existing_categories: list[str] | None = None) -> str:
    """Format an item with PARA guidelines for Copilot to categorize.
    
    Returns structured text that Copilot can reason about.
    """
    lines = [
        "# Categorize This Item\n",
        f"**Title:** {item.meta.title}",
        f"**Source:** {item.meta.source}",
        f"**Current location:** {item.path or 'Inbox (uncategorized)'}",
        f"**Tags:** {', '.join(item.meta.tags) if item.meta.tags else 'none'}",
        f"\n**Content:**\n{item.content}\n",
        "---\n",
        PARA_GUIDELINES,
    ]
    
    if existing_categories:
        lines.append(f"\n**Existing folders you can place it in:**")
        for cat in existing_categories:
            lines.append(f"  - {cat}")
    
    lines.append(
        "\n**To move this item, use:** "
        f"`move_item` with path='{item.path}' and new_path='<Category>/<subfolder>/{item.filename}'"
    )
    
    return "\n".join(lines)
