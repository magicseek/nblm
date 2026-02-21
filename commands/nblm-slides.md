---
description: Generate and manage NotebookLM slide decks (PDF output)
argument-hint: <subcommand> [options]
allowed-tools: Bash
---

Generate slide deck presentations from your NotebookLM notebook. Output is PDF.

$IF($ARGUMENTS,
  Parse the subcommand from: "$ARGUMENTS"

  **generate** → Generate a slide deck:
  `cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py artifact_manager.py generate-slides $ARGUMENTS`

  **generate --wait --output <path>** → Generate and download:
  `cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py artifact_manager.py generate-slides --wait --output "$OUTPUT" $EXTRA_ARGS`

  **download <path>** → Download latest slide deck:
  `cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py artifact_manager.py download "$ARGUMENTS" --type slide-deck`

  **list** → List all slide decks:
  `cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py artifact_manager.py list --type slide-deck`

  **status --task-id <id>** → Check generation status:
  `cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py artifact_manager.py status $ARGUMENTS`

  If subcommand not recognized, show usage below.,

  Show usage:

  Usage: /nblm-slides <subcommand> [options]

  Subcommands:
    generate    Generate a slide deck from the active notebook
    download    Download a slide deck as PDF
    list        List generated slide decks
    status      Check generation status

  Examples:
    /nblm-slides generate --wait --output ./presentation.pdf
    /nblm-slides generate --format PRESENTER_SLIDES --instructions "Focus on key findings"
    /nblm-slides generate --length SHORT --wait --output ./short-deck.pdf
    /nblm-slides download ./presentation.pdf
    /nblm-slides list
    /nblm-slides status --task-id <task-id>
)

## generate

Generate a slide deck from the active (or specified) notebook.

```
python scripts/run.py artifact_manager.py generate-slides [options]
```

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--format` | `DETAILED_DECK`, `PRESENTER_SLIDES` | `DETAILED_DECK` | Slide style |
| `--length` | `SHORT`, `DEFAULT` | `DEFAULT` | Deck length |
| `--instructions` | text | — | Custom generation instructions |
| `--wait` | flag | — | Wait for completion before returning |
| `--output` / `-o` | path | — | Download path as PDF (requires `--wait`) |
| `--timeout` | seconds | `600` | Max wait time |
| `--notebook-id` | ID | active | Target notebook |

### Formats

| Format | Description |
|--------|-------------|
| `DETAILED_DECK` | Full slide deck with detailed content per slide |
| `PRESENTER_SLIDES` | Concise presenter-style slides |

### Examples

```bash
# Generate and wait, download as PDF
python scripts/run.py artifact_manager.py generate-slides --wait --output ./presentation.pdf

# Presenter format with custom instructions
python scripts/run.py artifact_manager.py generate-slides \
  --format PRESENTER_SLIDES \
  --instructions "Focus on the methodology section" \
  --wait --output ./presenter.pdf

# Short deck for a specific notebook
python scripts/run.py artifact_manager.py generate-slides \
  --length SHORT \
  --notebook-id <notebook-id> \
  --wait --output ./summary.pdf

# Start generation without waiting (get task ID)
python scripts/run.py artifact_manager.py generate-slides --format DETAILED_DECK
```

## download

Download a previously generated slide deck as PDF.

```
python scripts/run.py artifact_manager.py download <output-path> --type slide-deck [--artifact-id ID] [--notebook-id ID]
```

```bash
# Download latest slide deck
python scripts/run.py artifact_manager.py download ./presentation.pdf --type slide-deck

# Download specific artifact
python scripts/run.py artifact_manager.py download ./deck.pdf --type slide-deck --artifact-id <artifact-id>
```

## list

List all slide deck artifacts in the active notebook.

```
python scripts/run.py artifact_manager.py list --type slide-deck [--notebook-id ID]
```

```bash
python scripts/run.py artifact_manager.py list --type slide-deck
python scripts/run.py artifact_manager.py list --type slide-deck --notebook-id <notebook-id>
```

## status

Check the status of an in-progress slide deck generation task.

```
python scripts/run.py artifact_manager.py status --task-id <task-id> [--notebook-id ID] [--json]
```

```bash
python scripts/run.py artifact_manager.py status --task-id <task-id>
python scripts/run.py artifact_manager.py status --task-id <task-id> --json
```

## Notes

- Output is always **PDF** — no PPTX, Google Slides, or editable format available
- No `LONG` length option (unlike audio); only `SHORT` and `DEFAULT`
- Generation can take several minutes depending on notebook size
- Use `--wait` with `--output` to generate and download in one step
- Without `--wait`, you get a task ID to poll with `status`
