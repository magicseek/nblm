# Authentication Notes

This skill uses the `agent-browser` CLI to automate NotebookLM. Authentication is handled by a visible browser session and persisted by the CLI under a named session.

## How Authentication Works

- `auth_manager.py setup` launches a headed browser.
- You log in to Google manually.
- The `agent-browser` session (default: `notebooklm`) keeps cookies/storage for subsequent commands.
- The skill stores minimal metadata in `data/auth_info.json` and `data/agent_browser/session_id`.

## Troubleshooting Authentication

1. **Not authenticated**
   ```bash
   python scripts/run.py auth_manager.py setup
   ```

2. **Reset and re-authenticate**
   ```bash
   python scripts/run.py auth_manager.py clear
   python scripts/run.py auth_manager.py setup
   ```

3. **Missing browsers**
   ```bash
   npm install
   npx agent-browser install
   ```

## Security Notes

- All browser activity runs locally.
- The `data/` directory contains sensitive auth metadata. Never commit it.
- Use a dedicated Google account for automation if you prefer extra isolation.
