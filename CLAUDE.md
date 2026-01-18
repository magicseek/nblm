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
python scripts/run.py auth_manager.py setup     # Initial login (browser visible)
python scripts/run.py auth_manager.py status    # Check auth
python scripts/run.py auth_manager.py reauth    # Re-authenticate
python scripts/run.py auth_manager.py clear     # Clear auth data

# Notebook Library
python scripts/run.py notebook_manager.py list
python scripts/run.py notebook_manager.py add --url URL --name NAME --description DESC --topics TOPICS
python scripts/run.py notebook_manager.py search --query KEYWORD
python scripts/run.py notebook_manager.py activate --id ID
python scripts/run.py notebook_manager.py remove --id ID

# Query
python scripts/run.py ask_question.py --question "..." [--notebook-id ID] [--notebook-url URL] [--show-browser]

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
├── auth_manager.py       # Google authentication and session persistence
├── notebook_manager.py   # CRUD operations for notebook library (library.json)
├── agent_browser_client.py # Unix socket client for agent-browser daemon
├── cleanup_manager.py    # Data cleanup with preservation options
├── config.py             # Configuration management
└── setup_environment.py  # Automatic venv and dependency installation

data/                     # Git-ignored local storage
├── library.json          # Notebook metadata
├── auth_info.json        # Authentication status
└── agent_browser/        # Session metadata (session_id)

references/               # Extended documentation
├── api_reference.md
├── troubleshooting.md
└── usage_patterns.md
```

**Key Flow:** `run.py` → ensures Python/Node deps → `ask_question.py` → `agent_browser_client.py` → agent-browser daemon

## Key Dependencies

- **python-dotenv==1.0.0**: Environment configuration
- **agent-browser** (npm): Browser automation daemon
- **Node.js**: Required to run the daemon

## Testing

No automated test suite. Testing is manual/functional via the scripts.

## Important Notes

- Authentication requires a visible browser session (`--show-browser`)
- Free tier rate limit: 50 queries/day
- `data/` directory contains sensitive auth data - never commit
- Each question is independent (stateless model)
- Answers include follow-up prompt to encourage comprehensive research
