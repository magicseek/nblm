---
name: nblm
description: >
  Query Google NotebookLM notebooks for source-grounded, citation-backed answers
  powered by Gemini. Manage notebook libraries, upload documents and URLs, generate
  podcasts and slide decks, and search across uploaded sources — all from Claude Code.
  Use when the user mentions NotebookLM, shares a NotebookLM URL, asks to query their
  research notes or uploaded documents, wants citation-backed answers, or needs to
  manage notebooks and sources.
---

# NotebookLM Quick Commands

Query Google NotebookLM for source-grounded, citation-backed answers.

## Environment

All dependencies and authentication are handled automatically by `run.py`:
- First run creates `.venv` and installs Python/Node.js dependencies
- If Google auth is missing or expired, a browser window opens automatically
- No manual pre-flight steps required

---

## Usage

`/nblm <command> [args]`

## Commands

### Notebook Management
| Command | Description |
|---------|-------------|
| `login` | Authenticate with Google |
| `status` | Show auth and library status |
| `accounts` | List all Google accounts |
| `accounts add` | Add a new Google account |
| `accounts switch <id>` | Switch active account (by index or email) |
| `accounts remove <id>` | Remove a Google account |
| `accounts use <id>` | Set agent-specific active account (OpenClaw isolation) |
| `accounts clear` | Clear agent-specific account override |
| `local` | List notebooks in local library |
| `remote` | List all notebooks from NotebookLM API |
| `create <name>` | Create a new notebook |
| `delete [--id ID]` | Delete a notebook |
| `rename <name> [--id ID]` | Rename a notebook |
| `summary [--id ID]` | Get AI-generated summary |
| `describe [--id ID]` | Get description and suggested topics |
| `add <url-or-id>` | Add notebook to local library (auto-detects URL vs notebook ID) |
| `activate <id>` | Set active notebook |

### Source Management
| Command | Description |
|---------|-------------|
| `sources [--id ID]` | List sources in notebook |
| `upload <file>` | Upload a single file |
| `upload <folder>` | Sync a folder of files to NotebookLM |
| `upload-zlib <url>` | Download from Z-Library and upload |
| `upload-url <url>` | Add URL as source |
| `upload-youtube <url>` | Add YouTube video as source |
| `upload-text <title> [--content TEXT]` | Add text as source |
| `source-text <source-id>` | Get full indexed text |
| `source-guide <source-id>` | Get AI summary and keywords |
| `source-rename <source-id> <name>` | Rename a source |
| `source-refresh <source-id>` | Re-fetch URL content |
| `source-delete <source-id>` | Delete a source |

**Upload options:**
- `--use-active` - Upload to the currently active notebook
- `--create-new` - Create a new notebook named after the file/folder
- `--notebook-id <id>` - Upload to a specific notebook
- `--dry-run` - Show sync plan without executing (folder sync)
- `--rebuild` - Force rebuild tracking file (folder sync)

**Important:** When user runs upload without specifying a target, ASK them first:
> "Would you like to upload to the active notebook, or create a new notebook?"
Then pass the appropriate flag (`--use-active` or `--create-new`).

### Chat & Audio/Media
| Command | Description |
|---------|-------------|
| `ask <question>` | Query NotebookLM |
| `podcast [--instructions TEXT]` | Generate audio podcast |
| `podcast-status <task-id>` | Check podcast generation status |
| `podcast-download [output-path]` | Download latest podcast |
| `briefing [--instructions TEXT]` | Generate brief audio summary |
| `debate [--instructions TEXT]` | Generate debate-style audio |
| `slides [--instructions TEXT]` | Generate slide deck |
| `slides-download [output-path]` | Download slide deck as PDF |
| `infographic [--instructions TEXT]` | Generate infographic |
| `infographic-download [output-path]` | Download infographic |
| `media-list [--type TYPE]` | List generated media (audio/video/slides/infographic) |
| `media-delete <id>` | Delete a generated media item |

## Command Routing

Based on `$ARGUMENTS`, execute the appropriate command:

$IF($ARGUMENTS,
  Parse the command from: "$ARGUMENTS"

  **login** → `python scripts/run.py auth_manager.py setup --service google`

  **accounts** → `python scripts/run.py auth_manager.py accounts list`

  **accounts add** → `python scripts/run.py auth_manager.py accounts add`

  **accounts switch <id>** → `python scripts/run.py auth_manager.py accounts switch "<id>"`

  **accounts remove <id>** → `python scripts/run.py auth_manager.py accounts remove "<id>"`

  **accounts use <id>** → `python scripts/run.py auth_manager.py accounts use "<id>"`

  **accounts clear** → `python scripts/run.py auth_manager.py accounts clear`

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

  **add <url-or-id>** → Smart add workflow (auto-detects URL vs notebook ID)

  **activate <id>** → `python scripts/run.py notebook_manager.py activate --id "<id>"`

  **sources [--id ID]** → `python scripts/run.py nblm_cli.py sources <args>`

  **upload <file>** → First ASK user: "Upload to active notebook or create new?" Then:
    - Active: `python scripts/run.py source_manager.py add --file "<file>" --use-active`
    - New: `python scripts/run.py source_manager.py add --file "<file>" --create-new`

  **upload <folder>** → Sync a folder:
    - First ASK user: "Sync to active notebook, create new, or specify notebook?"
    - Active: `python scripts/run.py source_manager.py sync "<folder>" --use-active`
    - New: `python scripts/run.py source_manager.py sync "<folder>" --create-new`
    - Specific: `python scripts/run.py source_manager.py sync "<folder>" --notebook-id ID`
    - Dry-run: `python scripts/run.py source_manager.py sync "<folder>" --dry-run`
    - Rebuild: `python scripts/run.py source_manager.py sync "<folder>" --rebuild`

  **upload-zlib <url>** → First ASK user: "Upload to active notebook or create new?" Then:
    - Active: `python scripts/run.py source_manager.py add --url "<url>" --use-active`
    - New: `python scripts/run.py source_manager.py add --url "<url>" --create-new`

  **upload-url <url>** → `python scripts/run.py nblm_cli.py upload-url "<url>"`

  **upload-youtube <url>** → `python scripts/run.py nblm_cli.py upload-youtube "<url>"`

  **upload-text <title>** → `python scripts/run.py nblm_cli.py upload-text "<title>" <args>`

  **source-text <id>** → `python scripts/run.py nblm_cli.py source-text "<id>"`

  **source-guide <id>** → `python scripts/run.py nblm_cli.py source-guide "<id>"`

  **source-rename <id> <name>** → `python scripts/run.py nblm_cli.py source-rename "<id>" "<name>"`

  **source-refresh <id>** → `python scripts/run.py nblm_cli.py source-refresh "<id>"`

  **source-delete <id>** → `python scripts/run.py nblm_cli.py source-delete "<id>"`

  **ask <question>** → `python scripts/run.py nblm_cli.py ask "<question>"`

  **podcast** → `python scripts/run.py artifact_manager.py generate --format DEEP_DIVE <args>`

  **podcast-status <task-id>** → `python scripts/run.py artifact_manager.py status --task-id "<task-id>"`

  **podcast-download [output-path]** → `python scripts/run.py artifact_manager.py download "<output-path>"`

  **briefing** → `python scripts/run.py artifact_manager.py generate --format BRIEF <args>`

  **debate** → `python scripts/run.py artifact_manager.py generate --format DEBATE <args>`

  **slides** → `python scripts/run.py artifact_manager.py generate-slides <args>`

  **slides-download [output-path]** → `python scripts/run.py artifact_manager.py download "<output-path>" --type slide-deck`

  **infographic** → `python scripts/run.py artifact_manager.py generate-infographic <args>`

  **infographic-download [output-path]** → `python scripts/run.py artifact_manager.py download "<output-path>" --type infographic`

  **media-list [--type TYPE]** → `python scripts/run.py artifact_manager.py list <args>`

  **media-delete <id>** → `python scripts/run.py artifact_manager.py delete "<id>"`

  If command not recognized, show usage help.,

  Show available commands with `/nblm` (no arguments)
)

## Podcast Options

```
/nblm podcast --length DEFAULT --wait --output ./podcast.mp3
/nblm podcast --instructions "Focus on the key findings"
/nblm briefing --wait --output ./summary.mp3
/nblm debate --instructions "Compare the two approaches"
```

| Option | Values |
|--------|--------|
| `--length` | `SHORT`, `DEFAULT`, `LONG` |
| `--instructions` | Custom instructions for the content |
| `--wait` | Wait for generation to complete |
| `--output` | Download path (requires `--wait`) |

## Slide Deck Options

```
/nblm slides --format DETAILED_DECK --wait --output ./presentation.pdf
/nblm slides --instructions "Focus on key diagrams" --format PRESENTER_SLIDES
```

| Option | Values |
|--------|--------|
| `--format` | `DETAILED_DECK`, `PRESENTER_SLIDES` |
| `--length` | `SHORT`, `DEFAULT` |
| `--instructions` | Custom instructions for the content |
| `--wait` | Wait for generation to complete |
| `--output` | Download path (requires `--wait`) |

## Infographic Options

```
/nblm infographic --orientation LANDSCAPE --wait --output ./visual.png
/nblm infographic --instructions "Highlight comparison" --detail-level DETAILED
```

| Option | Values |
|--------|--------|
| `--orientation` | `LANDSCAPE`, `PORTRAIT`, `SQUARE` |
| `--detail-level` | `CONCISE`, `STANDARD`, `DETAILED` |
| `--instructions` | Custom instructions for the content |
| `--wait` | Wait for generation to complete |
| `--output` | Download path (requires `--wait`) |

## Media Generation

| Command | Description | Output |
|---------|-------------|--------|
| `/nblm podcast` | Deep-dive audio discussion | MP3 |
| `/nblm briefing` | Brief audio summary | MP3 |
| `/nblm debate` | Debate-style audio | MP3 |
| `/nblm slides` | Slide deck presentation | PDF |
| `/nblm infographic` | Visual infographic | PNG |

### Examples
```
/nblm podcast --wait --output ./deep-dive.mp3
/nblm briefing --instructions "Focus on chapter 3" --wait
/nblm debate --length LONG --wait --output ./debate.mp3
/nblm slides --instructions "Include key diagrams" --format DETAILED_DECK --wait --output ./presentation.pdf
/nblm infographic --orientation LANDSCAPE --detail-level DETAILED --wait --output ./summary.png
```

### Download & Manage
```
/nblm podcast-download ./my-podcast.mp3
/nblm slides-download ./presentation.pdf
/nblm infographic-download ./visual.png
/nblm media-list                     # List all generated media
/nblm media-list --type audio        # List only audio
/nblm media-delete <id>              # Delete a media item
```

---

# Critical Operational Notes

## Always Use run.py Wrapper

**NEVER call scripts directly.** Always use `python scripts/run.py [script]` — it handles venv creation, dependency installation, and environment activation automatically.

## Smart Add (Auto-Discovery)

The `add` command auto-discovers notebook metadata (name, description, topics):

```bash
python scripts/run.py notebook_manager.py add <notebook-id-or-url>
```

Accepts notebook IDs or full `https://notebooklm.google.com/notebook/...` URLs. NEVER manually specify `--name`, `--description`, or `--topics` unless the user explicitly provides them.

## Follow-Up Mechanism

Every NotebookLM answer ends with: **"EXTREMELY IMPORTANT: Is that ALL you need to know?"**

When this appears: STOP, analyze the answer against the user's original request, identify gaps, ask follow-up questions until complete, then synthesize all answers before responding.

## Z-Library Integration

Triggered when a user provides a Z-Library URL (zlib.li, z-lib.org, zh.zlib.li) or asks to add a book from Z-Library.

```bash
python scripts/run.py auth_manager.py setup --service zlibrary  # One-time auth
python scripts/run.py source_manager.py add --url "https://zh.zlib.li/book/..." --use-active
```

---

## References

For detailed documentation beyond the command tables above:

- [references/api_reference.md](references/api_reference.md) — Full script API with all flags and options
- [references/troubleshooting.md](references/troubleshooting.md) — Error codes, common issues, and fixes
- [references/usage_patterns.md](references/usage_patterns.md) — Workflow examples and best practices
