---
agent: "agent"
tools: ["second-brain"]
description: "Sync all external sources (bookmarks, OneDrive, Teams) and report what's new."
---

# Sync All Sources Agent

You are syncing all external data sources into the Second Brain. Run each sync and report results.

## Steps

### 1. Bookmarks
Call `sync_bookmarks`.
Report how many were synced from each browser (Comet → personal, Edge → work).

### 2. OneDrive / SharePoint
Call `sync_onedrive` with days_back: 7.
Report files synced and their types.

### 3. Teams (if configured)
Call `sync_teams` with days_back: 3.
If authentication fails, note it and continue — don't block on it.

### 4. Summary
Report:
- Total new items across all sources
- Which stores received items (personal vs work)
- Recommend running inbox triage if many new items landed

## Error Handling
- If a sync fails, log the error and continue with the next source
- Never let one broken connector block the others
