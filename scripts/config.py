"""
Configuration for nblm
Centralizes constants, selectors, and paths
"""

from pathlib import Path
from typing import Optional
import os
import re
import tempfile

# Paths
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"
AUTH_DIR = DATA_DIR / "auth"
GOOGLE_AUTH_FILE = AUTH_DIR / "google.json"
ZLIBRARY_AUTH_FILE = AUTH_DIR / "zlibrary.json"
LIBRARY_FILE = DATA_DIR / "library.json"

# Multi-account Google auth structure
GOOGLE_AUTH_DIR = AUTH_DIR / "google"
GOOGLE_AUTH_INDEX = GOOGLE_AUTH_DIR / "index.json"

# Legacy path (for migration detection)
GOOGLE_AUTH_FILE_LEGACY = AUTH_DIR / "google.json"


def _sanitize_agent_id(agent_id: str) -> str:
    """Sanitize agent ID for use as a filesystem path component.

    Removes path traversal characters and other unsafe chars, limits length.
    Example: "my/agent/../evil" -> "myagentevil"
    """
    # Remove path separators and traversal sequences
    sanitized = re.sub(r"[/\\.]", "-", agent_id)
    # Remove any other characters that are unsafe in filenames
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", sanitized)
    # Collapse multiple dashes
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
    # Limit length
    return sanitized[:64] or "default"


def get_agent_id() -> Optional[str]:
    """Get the current agent ID from environment variables.

    Priority: NBLM_AGENT_ID > OPENCLAW_AGENT > AGENT_NAME
    Returns None if no agent ID is set.
    """
    return (
        os.environ.get("NBLM_AGENT_ID")
        or os.environ.get("OPENCLAW_AGENT")
        or os.environ.get("AGENT_NAME")
        or None
    )


def get_agent_config_dir() -> Path:
    """Get the per-agent config directory.

    Returns DATA_DIR / "agents" / <agent_id> if an agent ID is set,
    otherwise returns DATA_DIR.
    """
    agent_id = get_agent_id()
    if agent_id:
        return DATA_DIR / "agents" / _sanitize_agent_id(agent_id)
    return DATA_DIR


def get_agent_active_account_file() -> Path:
    """Get the path to the active account file for the current agent."""
    return get_agent_config_dir() / "active_account.json"


# Set NOTEBOOKLM_HOME to use our auth directory for notebooklm-py
# This ensures download methods find our storage_state.json
os.environ.setdefault("NOTEBOOKLM_HOME", str(AUTH_DIR))

# Agent-browser configuration
AGENT_BROWSER_PROFILE_DIR = DATA_DIR / "agent_browser" / "profile"
AGENT_BROWSER_SESSION_FILE = DATA_DIR / "agent_browser" / "session_id"
AGENT_BROWSER_SOCKET_DIR = Path(tempfile.gettempdir())
DEFAULT_SESSION_ID = "notebooklm"
AGENT_BROWSER_ACTIVITY_FILE = DATA_DIR / "agent_browser" / "last_activity.json"
AGENT_BROWSER_WATCHDOG_PID_FILE = DATA_DIR / "agent_browser" / "watchdog.pid"
AGENT_BROWSER_STATE_FILE = DATA_DIR / "agent_browser" / "storage_state.json"
AGENT_BROWSER_IDLE_TIMEOUT_SECONDS = int(
    os.environ.get("AGENT_BROWSER_IDLE_TIMEOUT_SECONDS", "600")
)
AGENT_BROWSER_WATCHDOG_INTERVAL_SECONDS = int(
    os.environ.get("AGENT_BROWSER_WATCHDOG_INTERVAL_SECONDS", "30")
)

# NotebookLM token staleness threshold
NOTEBOOKLM_TOKEN_STALENESS_DAYS = 7

# NotebookLM Selectors
QUERY_INPUT_SELECTORS = [
    "textarea.query-box-input",  # Primary
    'textarea[aria-label="Feld für Anfragen"]',  # Fallback German
    'textarea[aria-label="Input for queries"]',  # Fallback English
]

RESPONSE_SELECTORS = [
    ".to-user-container .message-text-content",  # Primary
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
]

# Timeouts
LOGIN_TIMEOUT_MINUTES = 10
QUERY_TIMEOUT_SECONDS = 120
PAGE_LOAD_TIMEOUT = 30000
