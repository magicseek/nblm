---
description: Ask a question to your NotebookLM notebook
argument-hint: <question> [--notebook-id ID]
allowed-tools: Bash
---

Ask a question to NotebookLM and get a source-grounded answer with citations.

$IF($ARGUMENTS,
  Run: !`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py ask_question.py --question "$ARGUMENTS"`

  Present the answer clearly. If the answer suggests follow-up questions, offer to ask them.,

  ERROR: Please provide a question. Usage: /nblm-ask <your question> [--notebook-id ID]
)
