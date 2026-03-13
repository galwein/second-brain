"""PARA categorization helpers for Copilot-native AI.

Instead of calling an external LLM, these helpers format item content
and PARA methodology rules as rich context. Copilot (the LLM interface)
does the actual reasoning.
"""
from second_brain.models import Item, ParaCategory


PARA_GUIDELINES = """## PARA Methodology Guide

**Projects** — Active endeavors with a specific goal and deadline.
- Has a clear end state (can be "done")
- Has a timeline or deadline
- Examples: "Website redesign", "Q1 report", "Move to new apartment"

**Areas** — Ongoing responsibilities with no end date.
- Requires continuous maintenance/attention
- Has a standard to uphold
- Examples: "Health", "Finances", "Career development", "Team management"

**Resources** — Topics of interest or reference material.
- Information you want to save for future reference
- Topics you're learning about or interested in
- Examples: "Python tips", "Recipes", "Design inspiration", "Research papers"

**Archive** — Completed or inactive items.
- Finished projects
- Areas you no longer maintain
- Resources no longer relevant
- Anything you want to keep but don't actively need"""


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
