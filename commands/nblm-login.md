---
description: Authenticate with Google for NotebookLM access
allowed-tools: Bash
---

Authenticate with Google for NotebookLM access.

Run: !`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py auth_manager.py setup --service google`

After authentication completes, confirm the status and inform the user they can now use other nblm commands.
