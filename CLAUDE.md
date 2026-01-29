# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ IRON RULE - NotebookLM Usage

**When working in this repository and needing to reference or query NotebookLM, you MUST use the skill provided by this repo itself.** Do not use external NotebookLM tools or services - always use the scripts and tooling defined here.

This is a non-negotiable project law.

## Project Overview

nblm - enables AI coding agents to query Google NotebookLM for source-grounded, citation-backed answers. Uses the agent-browser daemon (Node.js) and a Unix socket protocol for automation.

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

# Multi-Account Management (Google)
python scripts/run.py auth_manager.py accounts list             # List all accounts
python scripts/run.py auth_manager.py accounts add              # Add new account
python scripts/run.py auth_manager.py accounts switch 1         # Switch by index
python scripts/run.py auth_manager.py accounts switch user@gmail.com  # Switch by email
python scripts/run.py auth_manager.py accounts remove 2         # Remove account

# Notebook Library (Smart Add auto-discovers metadata)
python scripts/run.py notebook_manager.py list
python scripts/run.py notebook_manager.py add <notebook-id-or-url>  # Auto-discovers name, description, topics
python scripts/run.py notebook_manager.py add <id> --name "Override Name" --topics "custom,topics"
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

# Artifacts (Audio/Podcast Generation)
python scripts/run.py artifact_manager.py list                              # List all artifacts
python scripts/run.py artifact_manager.py list --type audio                 # List audio only
python scripts/run.py artifact_manager.py get <artifact-id>                 # Get artifact details
python scripts/run.py artifact_manager.py delete <artifact-id>              # Delete artifact
python scripts/run.py artifact_manager.py generate --wait --output podcast.mp3  # Generate & download
python scripts/run.py artifact_manager.py generate --format DEBATE --length SHORT
python scripts/run.py artifact_manager.py generate --instructions "Focus on key findings"
python scripts/run.py artifact_manager.py status --task-id <task-id>        # Check generation status
python scripts/run.py artifact_manager.py download ./output.mp3             # Download latest audio
```

## Architecture

```
scripts/
├── run.py                # Entry point wrapper - handles venv and npm deps
├── ask_question.py       # Core query logic - uses agent-browser client
├── auth_manager.py       # Multi-service authentication and session persistence
├── notebook_manager.py   # CRUD operations for notebook library (library.json)
├── source_manager.py     # Source ingestion (file/Z-Library)
├── artifact_manager.py   # Audio/podcast generation and artifact management
├── agent_browser_client.py # Unix socket client for agent-browser daemon
├── cleanup_manager.py    # Data cleanup with preservation options
├── config.py             # Configuration management
└── setup_environment.py  # Automatic venv and dependency installation

scripts/zlibrary/
├── downloader.py         # Z-Library download automation
└── epub_converter.py     # EPUB to Markdown conversion

data/                     # Git-ignored local storage
├── library.json          # Notebook metadata (with account associations)
├── auth/                 # Per-service auth state
│   ├── google/           # Multi-account Google auth
│   │   ├── index.json    # Account index (active account, list)
│   │   └── *.json        # Per-account credentials
│   └── zlibrary.json
└── agent_browser/        # Session metadata (session_id)

references/               # Extended documentation
├── api_reference.md
├── troubleshooting.md
└── usage_patterns.md
```

**Key Flow:** `run.py` → ensures Python/Node deps → scripts use `NotebookLMWrapper` (async) → notebooklm-py API → agent-browser fallback

## Key Dependencies

### Foundation Libraries (Project Decision)

This skill uses **two foundation libraries** for NotebookLM integration:

1. **agent-browser** (npm - vercel-labs/agent-browser)
   - Headless browser automation CLI for AI agents
   - Used for: Authentication, token refresh, browser fallback for uploads, Z-Library automation
   - Key commands: `snapshot`, `click`, `fill`, `upload`, `navigate`, `evaluate`

2. **notebooklm-py** (pip - teng-lin/notebooklm-py)
   - Python async API client for Google NotebookLM
   - Used for: All NotebookLM API operations (notebooks, sources, chat, artifacts)
   - Key APIs:
     - `client.notebooks.create(name)` - Create notebooks
     - `client.notebooks.list()` - List notebooks
     - `client.sources.add_file(notebook_id, Path(...))` - Upload files
     - `client.sources.add_url(notebook_id, url)` - Add URL sources
     - `client.sources.add_youtube(notebook_id, url)` - Add YouTube
     - `client.sources.add_text(notebook_id, title, content)` - Add text
     - `client.sources.list(notebook_id)` - List sources
     - `client.chat(notebook_id, message)` - Query notebook
     - `client.artifacts.generate_audio(notebook_id, ...)` - Generate podcast
     - `client.artifacts.list(notebook_id)` - List artifacts
     - `client.artifacts.download_audio(notebook_id, path)` - Download audio

**Architecture:**
- API-first: All NotebookLM operations go through notebooklm-py
- Browser fallback: File uploads fall back to agent-browser on API failure
- Auth extraction: agent-browser extracts csrf_token/session_id for notebooklm-py
- Token refresh: Silent refresh on auth errors before retry

### Other Dependencies

- **python-dotenv==1.0.0**: Environment configuration
- **ebooklib / beautifulsoup4 / lxml**: EPUB conversion
- **Node.js**: Required to run the agent-browser daemon

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
- Free tier rate limit: 50 queries/day per Google account
- **Multi-account support:** Add multiple Google accounts to bypass rate limits
- `data/` directory contains sensitive auth data - never commit
- `data/auth/google/` stores per-account credentials with email in filename
- `NOTEBOOKLM_AUTH_TOKEN` + `NOTEBOOKLM_COOKIES` allow API fallback if the daemon cannot start
- Each question is independent (stateless model)
- Answers include follow-up prompt to encourage comprehensive research
- Notebooks are automatically associated with the account that added them
