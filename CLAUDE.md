# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotebookLM Claude Code Skill - enables Claude Code to query Google NotebookLM for source-grounded, citation-backed answers. Uses the agent-browser daemon (Node.js) and a Unix socket protocol for automation.

**Session Model:** Stateless per question; the daemon keeps browser state in memory until it is stopped.

## Development Commands

### Running Scripts (Always use run.py wrapper)
```bash
# CORRECT - Always use run.py:
python scripts/run.py auth_manager.py status
python scripts/run.py notebook_manager.py list
python scripts/run.py ask_question.py --question "..."

# WRONG - Will fail without venv:
python scripts/auth_manager.py status
```

The `run.py` wrapper automatically creates `.venv`, installs Python deps, and installs Node.js deps if needed.

### Manual Environment Setup (if automatic fails)
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
npm install
npm run install-browsers
```

### Common Script Commands
```bash
# Authentication
python scripts/run.py auth_manager.py setup                     # Default: Google
python scripts/run.py auth_manager.py setup --service zlibrary
python scripts/run.py auth_manager.py status                    # Show all services
python scripts/run.py auth_manager.py status --service zlibrary
python scripts/run.py auth_manager.py reauth --service google   # Re-authenticate
python scripts/run.py auth_manager.py clear --service zlibrary  # Clear auth data

# Notebook Library
python scripts/run.py notebook_manager.py list
python scripts/run.py notebook_manager.py add --url URL --name NAME --description DESC --topics TOPICS
python scripts/run.py notebook_manager.py search --query KEYWORD
python scripts/run.py notebook_manager.py activate --id ID
python scripts/run.py notebook_manager.py remove --id ID

# Query
python scripts/run.py ask_question.py --question "..." [--notebook-id ID] [--notebook-url URL] [--show-browser]

# Source Manager
python scripts/run.py source_manager.py add --url "https://zh.zlib.li/book/..."
python scripts/run.py source_manager.py add --file "/path/to/book.pdf"

# Cleanup
python scripts/run.py cleanup_manager.py                    # Preview
python scripts/run.py cleanup_manager.py --confirm          # Execute
python scripts/run.py cleanup_manager.py --preserve-library # Keep notebooks
```

## Architecture

```
scripts/
├── run.py                # Entry point wrapper - handles venv and npm deps
├── ask_question.py       # Core query logic - uses agent-browser client
├── auth_manager.py       # Multi-service authentication and session persistence
├── notebook_manager.py   # CRUD operations for notebook library (library.json)
├── source_manager.py     # Source ingestion (file/Z-Library)
├── agent_browser_client.py # Unix socket client for agent-browser daemon
├── cleanup_manager.py    # Data cleanup with preservation options
├── config.py             # Configuration management
└── setup_environment.py  # Automatic venv and dependency installation

scripts/zlibrary/
├── downloader.py         # Z-Library download automation
└── epub_converter.py     # EPUB to Markdown conversion

data/                     # Git-ignored local storage
├── library.json          # Notebook metadata
├── auth/                 # Per-service auth state
│   ├── google.json
│   └── zlibrary.json
└── agent_browser/        # Session metadata (session_id)

references/               # Extended documentation
├── api_reference.md
├── troubleshooting.md
└── usage_patterns.md
```

**Key Flow:** `run.py` → ensures Python/Node deps → `ask_question.py` → `agent_browser_client.py` → agent-browser daemon

## Key Dependencies

- **python-dotenv==1.0.0**: Environment configuration
- **ebooklib / beautifulsoup4 / lxml**: EPUB conversion
- **agent-browser** (npm): Browser automation daemon
- **notebooklm-kit** (npm): NotebookLM API client
- **Node.js**: Required to run the daemon

## Testing

No automated test suite. Testing is manual/functional via the scripts.

```bash
# Auth (Google + Z-Library)
python scripts/run.py auth_manager.py setup --service zlibrary
python scripts/run.py auth_manager.py status

# Download + upload
python scripts/run.py source_manager.py add --url "https://zh.zlib.li/book/..."
```

## Important Notes

- Authentication requires a visible browser session (`--show-browser`)
- Free tier rate limit: 50 queries/day
- `data/` directory contains sensitive auth data - never commit
- `data/auth/google.json` includes NotebookLM API token + cookies
- `NOTEBOOKLM_AUTH_TOKEN` + `NOTEBOOKLM_COOKIES` allow API fallback if the daemon cannot start
- Each question is independent (stateless model)
- Answers include follow-up prompt to encourage comprehensive research
