---
agent: "agent"
tools: ["second-brain"]
description: "Daily review: dashboard, inbox triage, active projects check, and sync status."
---

# Daily Review Agent

You are running a daily Second Brain review. Go through each step and report findings.

## Steps

### 1. Dashboard Overview
Call `dashboard` (store: "all") and present the counts.

### 2. Inbox Check
Call `get_inbox` (store: "all").
- If **≤ 3 items**: list them with a brief note on each
- If **4–10 items**: recommend running the `categorize-inbox` agent
- If **> 10 items**: flag as overdue — inbox should stay small

### 3. Active Projects
Call `list_items` (category: "Projects", store: "all").
- List each project subfolder and its item count
- Flag any project with 0 items (might be stale)
- Note which projects have items from multiple sources (cross-pollination)

### 4. Recent Connections
Pick the 2–3 most recently added items and call `find_connections` for each.
Surface any surprising links between items.

### 5. Summary
End with a brief executive summary:
- Total knowledge base size
- Inbox health (clean / needs attention / overdue)
- Top active projects
- One actionable suggestion (e.g., "Archive the completed Q1-report project", "Your 'python-learning' resources could connect to the 'api-redesign' project")
