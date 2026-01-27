#!/usr/bin/env python3
"""
Patchright-based Google Authentication for nblm

Uses Patchright (anti-detection Playwright fork) to bypass Google's
"This browser or app may not be secure" blocking for personal Gmail accounts.

Key techniques:
- Uses real Chrome executable (not Chrome for Testing)
- Persistent context maintains session
- No custom headers that trigger detection
- Patchright's anti-detection patches
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from config import (
    GOOGLE_AUTH_FILE,
    SKILL_DIR,
)

# NotebookLM URL
NOTEBOOKLM_URL = "https://notebooklm.google.com"


# Patchright browser profile directory
PATCHRIGHT_PROFILE_DIR = SKILL_DIR / "data" / "patchright-profile"


def _find_chrome_executable() -> Optional[str]:
    """Find the real Chrome executable path on the current platform."""
    import platform
    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif system == "Windows":
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    else:  # Linux
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/opt/google/chrome/chrome",
        ]

    for path in paths:
        if os.path.isfile(path):
            return path
    return None


def _extract_storage_state(context) -> Dict[str, Any]:
    """Extract cookies and localStorage from browser context."""
    # Get cookies
    cookies = context.cookies()

    # Get localStorage from NotebookLM origin
    origins = []
    try:
        page = context.pages[0] if context.pages else None
        if page and "notebooklm.google.com" in page.url:
            local_storage = page.evaluate("() => Object.entries(localStorage)")
            origins.append({
                "origin": "https://notebooklm.google.com",
                "localStorage": [{"name": k, "value": v} for k, v in local_storage]
            })
    except Exception:
        pass  # localStorage extraction is optional

    return {
        "cookies": cookies,
        "origins": origins,
    }


def _save_auth_state(storage_state: Dict[str, Any]) -> None:
    """Save authentication state to google.json."""
    GOOGLE_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Add timestamp
    storage_state["notebooklm_updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(GOOGLE_AUTH_FILE, "w") as f:
        json.dump(storage_state, f, indent=2)


def authenticate_with_patchright(timeout_seconds: int = 600) -> bool:
    """
    Perform Google authentication using Patchright.

    Opens a real Chrome browser for user to log in manually.
    Waits for successful authentication, then saves session.

    Args:
        timeout_seconds: Maximum time to wait for user to complete login

    Returns:
        True if authentication succeeded, False otherwise
    """
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        print("❌ Patchright not installed. Run: pip install patchright && patchright install chromium")
        return False

    # Find real Chrome executable
    chrome_path = _find_chrome_executable()
    if not chrome_path:
        print("❌ Google Chrome not found. Please install Chrome.")
        return False

    print("🔐 Opening Chrome for Google authentication...")
    print(f"   Using: {chrome_path}")
    print("   (Patchright anti-detection enabled)")
    print()

    PATCHRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Launch with anti-detection settings
        # Key: ignore_default_args removes --enable-automation flag
        # args disable additional automation indicators
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PATCHRIGHT_PROFILE_DIR),
            executable_path=chrome_path,  # Use actual installed Chrome
            headless=False,               # Must be visible for auth
            no_viewport=True,             # Don't override viewport
            ignore_default_args=[
                "--enable-automation",    # Removes automation banner
                "--enable-blink-features=AutomationControlled",
            ],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            # Don't add custom headers - triggers detection
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Navigate to NotebookLM
        print(f"🌐 Navigating to {NOTEBOOKLM_URL}...")
        page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")

        # Wait for user to complete authentication
        print()
        print("⏳ Please complete login in the browser window...")
        print("   (This script will wait for you to finish)")
        print()

        start_time = time.time()
        authenticated = False

        while time.time() - start_time < timeout_seconds:
            try:
                current_url = page.url

                # Check if we've reached the authenticated NotebookLM page
                if "notebooklm.google.com" in current_url and "accounts.google.com" not in current_url:
                    # Verify we're not on sign-in page
                    if "/signin" not in current_url:
                        # Give page time to fully load
                        time.sleep(2)
                        authenticated = True
                        break

                time.sleep(1)
            except Exception:
                time.sleep(1)

        if authenticated:
            print("✅ Authentication successful!")

            # Extract and save storage state
            storage_state = _extract_storage_state(context)
            _save_auth_state(storage_state)

            print(f"   ✓ Saved auth state to {GOOGLE_AUTH_FILE.name}")

            # Also save Playwright-compatible storage state for notebooklm-py
            storage_state_file = SKILL_DIR / "data" / "auth" / "storage_state.json"
            context.storage_state(path=str(storage_state_file))
            print(f"   ✓ Saved storage_state.json for API client")
        else:
            print("❌ Authentication timed out")

        context.close()
        return authenticated


def clear_patchright_profile() -> bool:
    """Clear the Patchright browser profile for fresh auth."""
    import shutil

    if PATCHRIGHT_PROFILE_DIR.exists():
        shutil.rmtree(PATCHRIGHT_PROFILE_DIR)
        print(f"   ✓ Cleared Patchright profile")
        return True
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_patchright_profile()
    else:
        success = authenticate_with_patchright()
        sys.exit(0 if success else 1)
