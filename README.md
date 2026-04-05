# 🧠 Second Brain

A personal knowledge management system following the [PARA methodology](https://fortelabs.com/blog/para/), powered by AI and integrated with GitHub Copilot via the Model Context Protocol (MCP).

## Features

- **PARA Organization** — Projects, Areas, Resources, Archive structure for all your knowledge
- **Dual Stores** — Strict separation between personal (GitHub) and work (local) data
- **AI-Powered** — Copilot-native categorization, summarization, and connection finding
- **Copilot Integration** — Use directly from GitHub Copilot via MCP
- **Agent Prompts** — Reusable `.prompt.md` agents for inbox triage, daily review, and sync
- **Work Sync** — Microsoft Teams and OneDrive/SharePoint connectors

## Architecture

```
Copilot (MCP) ←→ MCP Server ←→ Storage Layer
                      ↕              ↕
             Formatter Layer    GitHub / Local FS
                      ↕
              Connectors (Teams, OneDrive, ADO)
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Git
- GitHub Copilot with MCP support (handles all AI reasoning — no separate API key needed)

### 2. Installation

```bash
# Clone this repo
git clone https://github.com/galwein/second-brain.git
cd second-brain

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configuration

```bash
# Create config directory
mkdir -p ~/.config/second-brain

# Copy example config
cp config.example.yaml ~/.config/second-brain/config.yaml

# Edit with your settings
nano ~/.config/second-brain/config.yaml
```

**Required settings:**
- `stores.personal.path` — Path to your personal data store (default: `~/second-brain-data/personal`)
- `stores.work.path` — Path to your work data store (default: `~/second-brain-data/work`)

**Optional settings:**
- `stores.personal.github_repo` — GitHub repo for personal data sync
- `microsoft.client_id` / `microsoft.tenant_id` — For Teams/OneDrive sync

> **Note:** AI features (categorization, summarization, connection-finding) are handled entirely by GitHub Copilot via MCP — no separate API key is required.

### 4. Initialize Data Stores

```bash
# Personal store (GitHub-backed)
mkdir -p ~/second-brain-data/personal
cd ~/second-brain-data/personal
git init
# Create PARA structure
mkdir -p Projects Areas Resources Archive Inbox .second-brain

# Work store (local only)
mkdir -p ~/second-brain-data/work
cd ~/second-brain-data/work
mkdir -p Projects Areas Resources Archive Inbox .second-brain
```

### 5. Connect to Copilot

Add to your VS Code settings or `.github/copilot/mcp.json`:

```json
{
  "servers": {
    "second-brain": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "second_brain.server"]
    }
  }
}
```

## Usage (via Copilot)

Once connected, ask Copilot things like:

### Adding Items
> "Add a note about the new API design to my personal second brain"
> "Save this meeting summary to my work second brain"

### Searching
> "Search my second brain for anything about authentication"
> "Find notes about project deadlines in my work store"

### Organizing
> "Show my inbox — what needs to be categorized?"
> "Categorize the item at Inbox/api-design.md"
> "Move Inbox/api-design.md to Projects/api-redesign/"

### AI Features
> "Summarize my notes about the Q1 planning"
> "What connections exist between my recent notes?"

### Dashboard
> "Show my second brain dashboard"

### Syncing (Work)
> "Sync my Teams messages from the last 3 days"
> "Sync recent OneDrive documents"

## MCP Tools Reference

| Tool | Description |
|------|-------------|
| `add_item` | Add a new item to the Inbox for later categorization |
| `search` | Search titles, content, and tags across stores |
| `get_item` | Retrieve a specific item by path |
| `list_items` | List items in a PARA category |
| `move_item` | Move an item between categories |
| `get_inbox` | Show uncategorized items in the Inbox |
| `categorize` | AI-powered PARA categorization of an item |
| `summarize` | AI-generated summary of an item |
| `sync_teams` | Sync messages from Microsoft Teams |
| `sync_onedrive` | Sync documents from OneDrive/SharePoint |
| `dashboard` | Overview of your Second Brain stats |

## PARA Methodology

| Category | What goes here | Examples |
|----------|---------------|----------|
| **Projects** | Active projects with goals & deadlines | "Website redesign", "Q1 report" |
| **Areas** | Ongoing responsibilities | "Health", "Finances", "Team management" |
| **Resources** | Topics of interest & reference | "Machine learning", "Cooking recipes" |
| **Archive** | Completed/inactive items | Old projects, outdated references |
| **Inbox** | New items awaiting categorization | Anything just captured |

## Item Format

Items are stored as Markdown files with YAML frontmatter:

```markdown
---
title: "My Note Title"
source: manual
store: personal
category: Resources/programming
tags: [python, tips]
created: 2025-03-13T12:00:00
summary: "Quick tips about Python async patterns"
---

# My Note Title

Your content here...
```

## Connectors

### Microsoft Teams (Work)
1. Register an app in Azure AD
2. Add `client_id` and `tenant_id` to config
3. Install Teams extras: `pip install -e ".[teams]"`
4. Use `sync_teams` tool — authenticates via device code flow

### OneDrive/SharePoint (Work)
1. Ensure OneDrive is mounted locally (macOS: auto-mounts to `~/Library/CloudStorage`)
2. Use `sync_onedrive` tool
3. Supports: .docx, .pptx, .xlsx, .pdf, .txt, .md, .csv

## Environment Variables

| Variable | Overrides |
|----------|-----------|
| `SECOND_BRAIN_GITHUB_TOKEN` | `stores.personal.github_token` |
| `SECOND_BRAIN_MS_CLIENT_ID` | `microsoft.client_id` |
| `SECOND_BRAIN_MS_TENANT_ID` | `microsoft.tenant_id` |

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/

# Run server directly
python -m second_brain.server
```

## Project Structure

```
src/second_brain/
├── server.py              # MCP server entry point
├── config.py              # Configuration management
├── models.py              # Data models (Item, ItemMeta, ParaCategory)
├── search.py              # Unified search engine
├── storage/               # Storage backends
│   ├── base.py            # Abstract interface
│   ├── github_storage.py  # Git-backed (personal)
│   └── local_storage.py   # Local filesystem (work)
├── formatters/            # Context formatters for Copilot reasoning
│   ├── categorizer.py     # PARA categorization context
│   ├── summarizer.py      # Content summarization context
│   └── connector_agent.py # Connection finding context
├── connectors/            # Data source connectors
│   ├── base.py            # Abstract interface
│   ├── teams.py           # Microsoft Teams
│   ├── onedrive.py        # OneDrive/SharePoint
│   ├── bookmarks.py       # Browser bookmarks (Comet/Edge)
│   └── ado.py             # Azure DevOps work items
└── tools/                 # MCP tool implementations
    ├── crud.py            # CRUD operations
    ├── para.py            # PARA-specific tools
    └── sync.py            # Connector sync tools
```

## Future Plans

- [x] Google Calendar integration
- [x] Browser bookmarks sync (Comet / Edge)
- [x] Azure DevOps work item sync
- [x] Office document extraction (.docx, .pptx, .xlsx, .pdf)
- [ ] X/Twitter bookmarks connector
- [ ] Facebook saved posts connector
- [ ] Semantic/vector search (ChromaDB)
- [ ] Browser extension for web clipping
- [ ] Periodic background sync

## License

MIT
