#!/usr/bin/env python3
"""
Authentication Manager for NotebookLM Skill
Handles Google authentication using agent-browser
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, AGENT_BROWSER_SESSION_FILE
from agent_browser_client import AgentBrowserClient, AgentBrowserError


class AuthManager:
    """Manage Google authentication for NotebookLM"""

    AUTH_INFO_FILE = DATA_DIR / "auth_info.json"

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        if not self.AUTH_INFO_FILE.exists():
            return False

        try:
            with open(self.AUTH_INFO_FILE) as f:
                info = json.load(f)
                return info.get("authenticated", False)
        except Exception:
            return False

    def get_auth_info(self) -> dict:
        """Get authentication info"""
        if not self.AUTH_INFO_FILE.exists():
            return {"authenticated": False}

        try:
            with open(self.AUTH_INFO_FILE) as f:
                return json.load(f)
        except Exception:
            return {"authenticated": False}

    def _save_auth_info(self, authenticated: bool, email: str = None):
        """Save authentication info"""
        info = {
            "authenticated": authenticated,
            "timestamp": datetime.now().isoformat(),
            "email": email
        }
        with open(self.AUTH_INFO_FILE, 'w') as f:
            json.dump(info, f, indent=2)

    def _save_session_id(self, session_id: str):
        """Save session ID for future use"""
        AGENT_BROWSER_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_BROWSER_SESSION_FILE, 'w') as f:
            f.write(session_id)

    def _load_session_id(self) -> str:
        """Load saved session ID"""
        if AGENT_BROWSER_SESSION_FILE.exists():
            with open(AGENT_BROWSER_SESSION_FILE) as f:
                return f.read().strip()
        return None

    def setup(self):
        """Interactive Google authentication setup"""
        print("🔐 Setting up Google authentication...")
        print("   A browser window will open for you to log in.")
        print()

        client = AgentBrowserClient(session_id="notebooklm", headed=True)

        try:
            client.connect()

            # Navigate to NotebookLM (will redirect to Google login if needed)
            client.navigate("https://notebooklm.google.com")
            time.sleep(2)

            snapshot = client.snapshot()

            if client.check_auth(snapshot):
                print("📄 Current page state:")
                print(snapshot[:1000])
                print()
                print("⏳ Please complete Google login in the browser window...")
                print("   (This script will wait for you to finish)")

                # Poll until authenticated
                for _ in range(300):  # 5 minute timeout
                    time.sleep(2)
                    snapshot = client.snapshot()

                    if not client.check_auth(snapshot):
                        # Check if we're on NotebookLM
                        if "notebooklm" in snapshot.lower() or "notebook" in snapshot.lower():
                            print()
                            print("✅ Authentication successful!")
                            self._save_auth_info(authenticated=True)
                            self._save_session_id(client.session_id)
                            return True

                print()
                print("❌ Authentication timeout")
                return False
            else:
                # Already authenticated
                print("✅ Already authenticated!")
                self._save_auth_info(authenticated=True)
                self._save_session_id(client.session_id)
                return True

        except AgentBrowserError as e:
            print(f"❌ [{e.code}]: {e.message}")
            print(f"🔧 Recovery: {e.recovery}")
            return False
        finally:
            client.disconnect()

    def validate(self) -> bool:
        """Validate current authentication is still valid"""
        print("🔍 Validating authentication...")

        session_id = self._load_session_id()
        if not session_id:
            print("❌ No saved session")
            return False

        client = AgentBrowserClient(session_id=session_id)

        try:
            client.connect()
            client.navigate("https://notebooklm.google.com")
            time.sleep(2)

            snapshot = client.snapshot()

            if client.check_auth(snapshot):
                print("❌ Authentication expired")
                self._save_auth_info(authenticated=False)
                return False
            else:
                print("✅ Authentication valid")
                self._save_auth_info(authenticated=True)
                return True

        except AgentBrowserError as e:
            print(f"⚠️ Validation error: {e.message}")
            return False
        finally:
            client.disconnect()

    def clear(self):
        """Clear all authentication data"""
        print("🧹 Clearing authentication data...")

        if self.AUTH_INFO_FILE.exists():
            self.AUTH_INFO_FILE.unlink()
            print("   ✓ Removed auth_info.json")

        if AGENT_BROWSER_SESSION_FILE.exists():
            AGENT_BROWSER_SESSION_FILE.unlink()
            print("   ✓ Removed session_id")

        print("✅ Authentication data cleared")
        print("   Note: Browser profile preserved. Run 'reauth' for full reset.")

    def status(self):
        """Show current authentication status"""
        info = self.get_auth_info()

        print("🔐 Authentication Status")
        print("=" * 40)

        if info.get("authenticated"):
            print(f"   Status: ✅ Authenticated")
            print(f"   Since: {info.get('timestamp', 'Unknown')}")
            if info.get('email'):
                print(f"   Email: {info.get('email')}")
        else:
            print(f"   Status: ❌ Not authenticated")
            print(f"   Run: python scripts/run.py auth_manager.py setup")

        session_id = self._load_session_id()
        if session_id:
            print(f"   Session: {session_id}")


def main():
    parser = argparse.ArgumentParser(description='Manage NotebookLM authentication')
    parser.add_argument('command', choices=['setup', 'status', 'validate', 'reauth', 'clear'],
                       help='Command to run')

    args = parser.parse_args()
    auth = AuthManager()

    if args.command == 'setup':
        success = auth.setup()
        sys.exit(0 if success else 1)
    elif args.command == 'status':
        auth.status()
    elif args.command == 'validate':
        success = auth.validate()
        sys.exit(0 if success else 1)
    elif args.command == 'reauth':
        auth.clear()
        success = auth.setup()
        sys.exit(0 if success else 1)
    elif args.command == 'clear':
        auth.clear()


if __name__ == "__main__":
    main()
