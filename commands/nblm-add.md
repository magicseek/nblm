---
description: Add an existing NotebookLM notebook to your library
argument-hint: --url <notebook-url> --name <name> --description <desc> --topics <topics>
allowed-tools: Bash
---

Add an existing NotebookLM notebook to your local library for easy access.

$IF($ARGUMENTS,
  Run: !`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py notebook_manager.py add $ARGUMENTS`

  Confirm the notebook was added and show its ID.,

  ERROR: Please provide notebook details.

  Usage: /nblm-add --url <notebook-url> --name <name> --description <desc> --topics <topics>

  Example: /nblm-add --url "https://notebooklm.google.com/notebook/abc123" --name "Research Notes" --description "My research project" --topics "research,notes"
)
