---
description: Set the active notebook for queries
argument-hint: <notebook-id>
allowed-tools: Bash
---

Set a notebook as the active default for queries.

$IF($1,
  Run: !`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py notebook_manager.py activate --id "$1"`

  Confirm which notebook is now active.,

  ERROR: Please provide a notebook ID. Usage: /nblm-activate <notebook-id>

  To see available notebooks, use /nblm-list
)
