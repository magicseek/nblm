---
name: nblm
description: Use this skill to query your Google NotebookLM notebooks directly from Claude Code for source-grounded, citation-backed answers from Gemini. Browser automation, library management, persistent auth. Drastically reduced hallucinations through document-only responses.
---

# NotebookLM Quick Commands

Query Google NotebookLM for source-grounded, citation-backed answers.

## ⚠️ MANDATORY: Pre-Flight Checks (Run BEFORE Any Command)

**On EVERY `/nblm` invocation, you MUST run these checks in order:**

### Step 1: Check Dependencies
```bash
# This command auto-installs Python venv, pip dependencies, and npm packages
python scripts/run.py --check-deps
```

If the above fails with "command not found" or missing dependencies:
```bash
# Install Python dependencies
cd /path/to/notebooklm-skill && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Install Node.js dependencies (required for browser automation)
cd /path/to/notebooklm-skill && npm install
```

### Step 2: Check Google Authentication
```bash
python scripts/run.py auth_manager.py status --service google
```

**If output shows "Not authenticated" or auth file missing:**
1. Inform user: "Google authentication required. A browser window will open for login."
2. Run: `python scripts/run.py auth_manager.py setup --service google`
3. Wait for user to complete login in browser
4. Verify: `python scripts/run.py auth_manager.py status --service google`

**Only proceed to execute the user's command after both checks pass.**

---

## Usage

`/nblm <command> [args]`

## Commands

### Notebook Management
| Command | Description |
|---------|-------------|
| `login` | Authenticate with Google |
| `status` | Show auth and library status |
| `local` | List notebooks in local library |
| `remote` | List all notebooks from NotebookLM API |
| `create <name>` | Create a new notebook |
| `delete [--id ID]` | Delete a notebook |
| `rename <name> [--id ID]` | Rename a notebook |
| `summary [--id ID]` | Get AI-generated summary |
| `describe [--id ID]` | Get description and suggested topics |
| `add <url>` | Add notebook to local library |
| `activate <id>` | Set active notebook |

### Source Management
| Command | Description |
|---------|-------------|
| `sources [--id ID]` | List sources in notebook |
| `upload <file>` | Upload local file (PDF, TXT, MD, DOCX) |
| `upload-zlib <url>` | Download from Z-Library and upload |
| `upload-url <url>` | Add URL as source |
| `upload-youtube <url>` | Add YouTube video as source |
| `upload-text <title> [--content TEXT]` | Add text as source |
| `source-text <source-id>` | Get full indexed text |
| `source-guide <source-id>` | Get AI summary and keywords |
| `source-rename <source-id> <name>` | Rename a source |
| `source-refresh <source-id>` | Re-fetch URL content |
| `source-delete <source-id>` | Delete a source |

### Chat & Audio
| Command | Description |
|---------|-------------|
| `ask <question>` | Query NotebookLM |
| `podcast [--instructions TEXT]` | Generate audio podcast |

## Command Routing

Based on `$ARGUMENTS`, execute the appropriate command:

$IF($ARGUMENTS,
  Parse the command from: "$ARGUMENTS"

  **login** → `python scripts/run.py auth_manager.py setup --service google`

  **status** → Run both:
  - `python scripts/run.py auth_manager.py status`
  - `python scripts/run.py notebook_manager.py list`

  **local** → `python scripts/run.py notebook_manager.py list`

  **remote** → `python scripts/run.py nblm_cli.py notebooks`

  **create <name>** → `python scripts/run.py nblm_cli.py create "<name>"`

  **delete [--id ID]** → `python scripts/run.py nblm_cli.py delete <args>`

  **rename <name> [--id ID]** → `python scripts/run.py nblm_cli.py rename "<name>" <args>`

  **summary [--id ID]** → `python scripts/run.py nblm_cli.py summary <args>`

  **describe [--id ID]** → `python scripts/run.py nblm_cli.py describe <args>`

  **add <url>** → Smart add workflow (query notebook first to discover metadata)

  **activate <id>** → `python scripts/run.py notebook_manager.py activate --id "<id>"`

  **sources [--id ID]** → `python scripts/run.py nblm_cli.py sources <args>`

  **upload <file>** → `python scripts/run.py source_manager.py add --file "<file>"`

  **upload-zlib <url>** → `python scripts/run.py source_manager.py add --url "<url>"`

  **upload-url <url>** → `python scripts/run.py nblm_cli.py upload-url "<url>"`

  **upload-youtube <url>** → `python scripts/run.py nblm_cli.py upload-youtube "<url>"`

  **upload-text <title>** → `python scripts/run.py nblm_cli.py upload-text "<title>" <args>`

  **source-text <id>** → `python scripts/run.py nblm_cli.py source-text "<id>"`

  **source-guide <id>** → `python scripts/run.py nblm_cli.py source-guide "<id>"`

  **source-rename <id> <name>** → `python scripts/run.py nblm_cli.py source-rename "<id>" "<name>"`

  **source-refresh <id>** → `python scripts/run.py nblm_cli.py source-refresh "<id>"`

  **source-delete <id>** → `python scripts/run.py nblm_cli.py source-delete "<id>"`

  **ask <question>** → `python scripts/run.py nblm_cli.py ask "<question>"`

  **podcast** → `python scripts/run.py nblm_cli.py podcast <args>`

  If command not recognized, show usage help.,

  Show available commands with `/nblm` (no arguments)
)

## Podcast Options

```
/nblm podcast --format DEEP_DIVE --length DEFAULT --wait --output ./podcast.mp4
```

Formats: `DEEP_DIVE`, `BRIEF`, `CRITIQUE`, `DEBATE`
Lengths: `SHORT`, `DEFAULT`, `LONG`

---

# Extended Documentation

## When to Use This Skill

Trigger when user:
- Mentions NotebookLM explicitly
- Shares NotebookLM URL (`https://notebooklm.google.com/notebook/...`)
- Asks to query their notebooks/documentation
- Wants to add documentation to NotebookLM library
- Uses phrases like "ask my NotebookLM", "check my docs", "query my notebook"

## ⚠️ CRITICAL: Add Command - Smart Discovery

When user wants to add a notebook without providing details:

**SMART ADD (Recommended)**: Query the notebook first to discover its content:
```bash
# Step 1: Query the notebook about its content
python scripts/run.py ask_question.py --question "What is the content of this notebook? What topics are covered? Provide a complete overview briefly and concisely" --notebook-url "[URL]"

# Step 2: Use the discovered information to add it
python scripts/run.py notebook_manager.py add --url "[URL]" --name "[Based on content]" --description "[Based on content]" --topics "[Based on content]"
```

**MANUAL ADD**: If user provides all details:
- `--url` - The NotebookLM URL
- `--name` - A descriptive name
- `--description` - What the notebook contains (REQUIRED!)
- `--topics` - Comma-separated topics (REQUIRED!)

NEVER guess or use generic descriptions! If details missing, use Smart Add to discover them.

## Critical: Always Use run.py Wrapper

**NEVER call scripts directly. ALWAYS use `python scripts/run.py [script]`:**

```bash
# ✅ CORRECT - Always use run.py:
python scripts/run.py auth_manager.py status
python scripts/run.py notebook_manager.py list
python scripts/run.py ask_question.py --question "..."

# ❌ WRONG - Never call directly:
python scripts/auth_manager.py status  # Fails without venv!
```

The `run.py` wrapper automatically:
1. Creates `.venv` if needed
2. Installs all dependencies
3. Activates environment
4. Executes script properly

## Core Workflow

### Step 1: Check Authentication Status
```bash
python scripts/run.py auth_manager.py status
```

If not authenticated, proceed to setup.

### Step 2: Authenticate (One-Time Setup)
```bash
# Browser MUST be visible for manual Google login
python scripts/run.py auth_manager.py setup
```

**Important:**
- Browser is VISIBLE for authentication
- Browser window opens automatically
- User must manually log in to Google
- Tell user: "A browser window will open for Google login"

### Step 3: Manage Notebook Library

```bash
# List all notebooks
python scripts/run.py notebook_manager.py list

# BEFORE ADDING: Ask user for metadata if unknown!
# "What does this notebook contain?"
# "What topics should I tag it with?"

# Add notebook to library (ALL parameters are REQUIRED!)
python scripts/run.py notebook_manager.py add \
  --url "https://notebooklm.google.com/notebook/..." \
  --name "Descriptive Name" \
  --description "What this notebook contains" \  # REQUIRED - ASK USER IF UNKNOWN!
  --topics "topic1,topic2,topic3"  # REQUIRED - ASK USER IF UNKNOWN!

# Search notebooks by topic
python scripts/run.py notebook_manager.py search --query "keyword"

# Set active notebook
python scripts/run.py notebook_manager.py activate --id notebook-id

# Remove notebook
python scripts/run.py notebook_manager.py remove --id notebook-id
```

### Quick Workflow
1. Check library: `python scripts/run.py notebook_manager.py list`
2. Ask question: `python scripts/run.py ask_question.py --question "..." --notebook-id ID`

### Step 4: Ask Questions

```bash
# Basic query (uses active notebook if set)
python scripts/run.py ask_question.py --question "Your question here"

# Query specific notebook
python scripts/run.py ask_question.py --question "..." --notebook-id notebook-id

# Query with notebook URL directly
python scripts/run.py ask_question.py --question "..." --notebook-url "https://..."

# Show browser for debugging
python scripts/run.py ask_question.py --question "..." --show-browser
```

## Follow-Up Mechanism (CRITICAL)

Every NotebookLM answer ends with: **"EXTREMELY IMPORTANT: Is that ALL you need to know?"**

**Required Claude Behavior:**
1. **STOP** - Do not immediately respond to user
2. **ANALYZE** - Compare answer to user's original request
3. **IDENTIFY GAPS** - Determine if more information needed
4. **ASK FOLLOW-UP** - If gaps exist, immediately ask:
   ```bash
   python scripts/run.py ask_question.py --question "Follow-up with context..."
   ```
5. **REPEAT** - Continue until information is complete
6. **SYNTHESIZE** - Combine all answers before responding to user

## Z-Library Integration

### Triggers
- User provides Z-Library URL (zlib.li, z-lib.org, zh.zlib.li)
- User says "download this book to NotebookLM"
- User says "add this book from Z-Library"

### Setup (One-Time)
```bash
# Authenticate with Z-Library
python scripts/run.py auth_manager.py setup --service zlibrary
```

### Commands
```bash
# Add book from Z-Library
python scripts/run.py source_manager.py add --url "https://zh.zlib.li/book/..."

# Check Z-Library auth status
python scripts/run.py auth_manager.py status --service zlibrary
```

## Script Reference

### Authentication Management (`auth_manager.py`)
```bash
python scripts/run.py auth_manager.py setup                    # Default: Google
python scripts/run.py auth_manager.py setup --service google
python scripts/run.py auth_manager.py setup --service zlibrary
python scripts/run.py auth_manager.py status                   # Show all services
python scripts/run.py auth_manager.py status --service zlibrary
python scripts/run.py auth_manager.py reauth --service google  # Re-authenticate
python scripts/run.py auth_manager.py clear --service zlibrary # Clear auth
```

### Notebook Management (`notebook_manager.py`)
```bash
python scripts/run.py notebook_manager.py add --url URL --name NAME --description DESC --topics TOPICS
python scripts/run.py notebook_manager.py list
python scripts/run.py notebook_manager.py search --query QUERY
python scripts/run.py notebook_manager.py activate --id ID
python scripts/run.py notebook_manager.py remove --id ID
python scripts/run.py notebook_manager.py stats
```

### Question Interface (`ask_question.py`)
```bash
python scripts/run.py ask_question.py --question "..." [--notebook-id ID] [--notebook-url URL] [--show-browser]
```

### Source Manager (`source_manager.py`)
```bash
python scripts/run.py source_manager.py add --url "https://zh.zlib.li/book/..."
python scripts/run.py source_manager.py add --file "/path/to/book.pdf"
python scripts/run.py source_manager.py add --url "..." --notebook-id NOTEBOOK_ID
```
Uploads wait for NotebookLM processing and print progress as `Ready: N/T`. Press Ctrl+C to stop waiting.
Local file uploads use browser automation and require Google authentication.
If browser automation is unavailable, set `NOTEBOOKLM_UPLOAD_MODE=text` to upload extracted text instead (PDFs require `pypdf`).

### Data Cleanup (`cleanup_manager.py`)
```bash
python scripts/run.py cleanup_manager.py                    # Preview cleanup
python scripts/run.py cleanup_manager.py --confirm          # Execute cleanup
python scripts/run.py cleanup_manager.py --preserve-library # Keep notebooks
```

### Watchdog Status (`auth_manager.py`)
```bash
python scripts/run.py auth_manager.py watchdog-status
```

## Environment Management

The virtual environment is automatically managed:
- First run creates `.venv` automatically
- Dependencies install automatically
- Node.js dependencies install automatically
- agent-browser daemon starts on demand and keeps browser state in memory
- daemon stops after 10 minutes of inactivity (any agent-browser command resets the timer)
- set `AGENT_BROWSER_OWNER_PID` to auto-stop when the agent process exits
- `scripts/run.py` sets `AGENT_BROWSER_OWNER_PID` to its parent PID by default
- Everything isolated in skill directory

Manual setup (only if automatic fails):
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
npm install
npm run install-browsers
```

## Data Storage

All data stored in `~/.claude/skills/notebooklm/data/`:
- `library.json` - Notebook metadata
- `auth/google.json` - Google auth state
- `auth/zlibrary.json` - Z-Library auth state
- `agent_browser/session_id` - Current daemon session ID
- `agent_browser/last_activity.json` - Last activity timestamp for idle shutdown
- `agent_browser/watchdog.pid` - Idle watchdog process ID

**Security:** Protected by `.gitignore`, never commit to git.

## Configuration

Optional `.env` file in skill directory:
```env
HEADLESS=false           # Browser visibility
SHOW_BROWSER=false       # Default browser display
STEALTH_ENABLED=true     # Human-like behavior
TYPING_WPM_MIN=160       # Typing speed
TYPING_WPM_MAX=240
DEFAULT_NOTEBOOK_ID=     # Default notebook
```

## Decision Flow

```
User mentions NotebookLM
    ↓
Check auth → python scripts/run.py auth_manager.py status
    ↓
If not authenticated → python scripts/run.py auth_manager.py setup
    ↓
Check/Add notebook → python scripts/run.py notebook_manager.py list/add (with --description)
    ↓
Activate notebook → python scripts/run.py notebook_manager.py activate --id ID
    ↓
Ask question → python scripts/run.py ask_question.py --question "..."
    ↓
See "Is that ALL you need?" → Ask follow-ups until complete
    ↓
Synthesize and respond to user
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ModuleNotFoundError | Use `run.py` wrapper |
| Authentication fails | Browser must be visible for setup! --show-browser |
| DAEMON_UNAVAILABLE | Ensure Node.js/npm installed, run `npm install`, retry |
| AUTH_REQUIRED | Run `python scripts/run.py auth_manager.py setup` |
| ELEMENT_NOT_FOUND | Verify notebook URL and re-run with fresh page load |
| Rate limit (50/day) | Wait or switch Google account |
| Browser crashes | `python scripts/run.py cleanup_manager.py --preserve-library` |
| Notebook not found | Check with `notebook_manager.py list` |

## Best Practices

1. **Always use run.py** - Handles environment automatically
2. **Check auth first** - Before any operations
3. **Follow-up questions** - Don't stop at first answer
4. **Browser visible for auth** - Required for manual login
5. **Include context** - Each question is independent
6. **Synthesize answers** - Combine multiple responses

## Limitations

- No session persistence (each question = new browser)
- Rate limits on free Google accounts (50 queries/day)
- Manual upload required (user must add docs to NotebookLM)
- Browser overhead (few seconds per question)

## Resources (Skill Structure)

**Important directories and files:**

- `scripts/` - All automation scripts (ask_question.py, notebook_manager.py, etc.)
- `data/` - Local storage for authentication and notebook library
- `references/` - Extended documentation:
  - `api_reference.md` - Detailed API documentation for all scripts
  - `troubleshooting.md` - Common issues and solutions
  - `usage_patterns.md` - Best practices and workflow examples
- `.venv/` - Isolated Python environment (auto-created on first run)
- `.gitignore` - Protects sensitive data from being committed
