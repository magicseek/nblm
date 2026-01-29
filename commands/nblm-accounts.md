---
description: Manage multiple Google accounts for NotebookLM
allowed-tools: Bash
---

Manage multiple Google accounts for NotebookLM access.

**Usage:** `/nblm accounts [action] [identifier]`

**Actions:**
- `list` (default) - List all configured Google accounts
- `add` - Add a new Google account (opens browser for login)
- `switch <index-or-email>` - Switch to a different account
- `remove <index-or-email>` - Remove an account

**Examples:**
- `/nblm accounts` - List all accounts
- `/nblm accounts add` - Add new account
- `/nblm accounts switch 2` - Switch to account #2
- `/nblm accounts switch user@gmail.com` - Switch by email
- `/nblm accounts remove 1` - Remove account #1

Based on the user's request, run the appropriate command:

For listing accounts (default):
!`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py auth_manager.py accounts list`

For adding a new account:
!`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py auth_manager.py accounts add`

For switching accounts (replace IDENTIFIER with the index or email):
!`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py auth_manager.py accounts switch IDENTIFIER`

For removing accounts (replace IDENTIFIER with the index or email):
!`cd ${CLAUDE_PLUGIN_ROOT} && python scripts/run.py auth_manager.py accounts remove IDENTIFIER`

After the command completes, summarize the result for the user.
