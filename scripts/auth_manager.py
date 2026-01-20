#!/usr/bin/env python3
"""
Authentication Manager for NotebookLM Skill
Handles Google authentication using agent-browser
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATA_DIR,
    AUTH_DIR,
    GOOGLE_AUTH_FILE,
    ZLIBRARY_AUTH_FILE,
    AGENT_BROWSER_SESSION_FILE,
    DEFAULT_SESSION_ID,
    AGENT_BROWSER_ACTIVITY_FILE,
    AGENT_BROWSER_WATCHDOG_PID_FILE,
    AGENT_BROWSER_IDLE_TIMEOUT_SECONDS
)
from agent_browser_client import AgentBrowserClient, AgentBrowserError


def _pid_is_alive(pid: int) -> bool:
    """Check whether a PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def get_watchdog_status() -> dict:
    """Return watchdog and daemon status details."""
    last_activity = None
    owner_pid = None
    if AGENT_BROWSER_ACTIVITY_FILE.exists():
        try:
            payload = json.loads(AGENT_BROWSER_ACTIVITY_FILE.read_text())
            last_activity = payload.get("timestamp")
            owner_pid = payload.get("owner_pid")
        except Exception:
            last_activity = None
            owner_pid = None

    idle_seconds = None
    if last_activity is not None:
        try:
            idle_seconds = max(0, time.time() - float(last_activity))
        except Exception:
            idle_seconds = None

    watchdog_pid = None
    if AGENT_BROWSER_WATCHDOG_PID_FILE.exists():
        try:
            watchdog_pid = int(AGENT_BROWSER_WATCHDOG_PID_FILE.read_text().strip())
        except Exception:
            watchdog_pid = None

    watchdog_alive = bool(watchdog_pid and _pid_is_alive(watchdog_pid))
    owner_alive = bool(owner_pid and _pid_is_alive(int(owner_pid)))
    daemon_running = AgentBrowserClient(session_id=DEFAULT_SESSION_ID)._daemon_is_running()

    return {
        "watchdog_pid": watchdog_pid,
        "watchdog_alive": watchdog_alive,
        "last_activity": last_activity,
        "idle_seconds": idle_seconds,
        "idle_timeout_seconds": AGENT_BROWSER_IDLE_TIMEOUT_SECONDS,
        "owner_pid": owner_pid,
        "owner_alive": owner_alive,
        "daemon_running": daemon_running
    }


class AuthManager:
    """Unified auth manager for multiple services"""

    SERVICES = {
        "google": {
            "file": GOOGLE_AUTH_FILE,
            "login_url": "https://notebooklm.google.com",
            "success_indicators": ["notebooklm", "notebook"]
        },
        "zlibrary": {
            "file": ZLIBRARY_AUTH_FILE,
            "login_url": "https://zh.zlib.li/",
            "success_indicators": ["logout", "退出"]
        }
    }

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        AUTH_DIR.mkdir(parents=True, exist_ok=True)

    def _get_service_config(self, service: str) -> dict:
        service = service or "google"
        if service not in self.SERVICES:
            raise ValueError(f"Unknown service: {service}")
        return self.SERVICES[service]

    def _auth_file(self, service: str) -> Path:
        return self._get_service_config(service)["file"]

    def _auth_timestamp(self, auth_file: Path) -> str:
        try:
            return datetime.fromtimestamp(auth_file.stat().st_mtime).isoformat()
        except Exception:
            return "Unknown"

    def is_authenticated(self, service: str = "google") -> bool:
        """Check if service has valid saved auth"""
        info = self.get_auth_info(service)
        return bool(info.get("authenticated"))

    def get_auth_info(self, service: str = "google") -> dict:
        """Get authentication info for a service"""
        auth_file = self._auth_file(service)
        if not auth_file.exists():
            return {"authenticated": False}

        try:
            payload = json.loads(auth_file.read_text())
        except Exception:
            return {"authenticated": False}

        authenticated = bool(payload.get("cookies") or payload.get("origins"))
        timestamp = self._auth_timestamp(auth_file)
        return {
            "authenticated": authenticated,
            "timestamp": timestamp
        }

    def save_auth(self, service: str = "google", client: AgentBrowserClient = None) -> bool:
        """Save current browser state for service"""
        owns_client = False
        if client is None:
            client = AgentBrowserClient(session_id=self._load_session_id() or DEFAULT_SESSION_ID)
            client.connect()
            owns_client = True

        try:
            payload = client.get_storage_state()
            if not payload:
                return False
            auth_file = self._auth_file(service)
            auth_file.parent.mkdir(parents=True, exist_ok=True)
            auth_file.write_text(json.dumps(payload))
            self._save_session_id(client.session_id)
            return True
        except Exception:
            return False
        finally:
            if owns_client:
                client.disconnect()

    def restore_auth(self, service: str = "google", client: AgentBrowserClient = None) -> bool:
        """Restore saved auth state to browser"""
        auth_file = self._auth_file(service)
        if not auth_file.exists():
            return False

        try:
            payload = json.loads(auth_file.read_text())
        except Exception:
            return False

        owns_client = False
        if client is None:
            client = AgentBrowserClient(session_id=self._load_session_id() or DEFAULT_SESSION_ID)
            client.connect()
            owns_client = True

        try:
            return client.set_storage_state(payload)
        finally:
            if owns_client:
                client.disconnect()

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

    def _snapshot_indicates_auth(self, service: str, snapshot: str, client: AgentBrowserClient) -> bool:
        if not snapshot:
            return False
        service_name = service or "google"
        snapshot_lower = snapshot.lower()
        if service_name == "google":
            if client.check_auth(snapshot):
                return False
        if service_name == "zlibrary":
            login_indicators = (
                "login",
                "log in",
                "sign in",
                "sign up",
                "register",
                "登录",
                "注册",
            )
            if any(indicator in snapshot_lower for indicator in login_indicators):
                return False
            indicators = self._get_service_config(service_name)["success_indicators"]
            if any(indicator in snapshot_lower for indicator in indicators):
                return True
            return True
        indicators = self._get_service_config(service_name)["success_indicators"]
        return any(indicator in snapshot_lower for indicator in indicators)

    def setup(self, service: str = "google"):
        """Interactive authentication setup for specified service"""
        service_config = self._get_service_config(service)
        print(f"🔐 Setting up {service} authentication...")
        print("   A browser window will open for you to log in.")
        print()

        client = AgentBrowserClient(session_id=DEFAULT_SESSION_ID, headed=True)

        try:
            client.connect()
            client.navigate(service_config["login_url"])
            time.sleep(2)

            snapshot = client.snapshot()

            if not self._snapshot_indicates_auth(service, snapshot, client):
                print("📄 Current page state:")
                print(snapshot[:1000])
                print()
                print("⏳ Please complete login in the browser window...")
                print("   (This script will wait for you to finish)")

                for _ in range(300):  # 5 minute timeout
                    time.sleep(2)
                    snapshot = client.snapshot()
                    if self._snapshot_indicates_auth(service, snapshot, client):
                        print()
                        print("✅ Authentication successful!")
                        self._save_session_id(client.session_id)
                        self.save_auth(service, client=client)
                        return True

                print()
                print("❌ Authentication timeout")
                return False

            print("✅ Already authenticated!")
            self._save_session_id(client.session_id)
            self.save_auth(service, client=client)
            return True

        except AgentBrowserError as e:
            print(f"❌ [{e.code}]: {e.message}")
            print(f"🔧 Recovery: {e.recovery}")
            return False
        finally:
            client.disconnect()

    def get_notebooklm_credentials(
        self,
        client: AgentBrowserClient = None,
        force_refresh: bool = False,
    ) -> dict:
        """Return NotebookLM auth token and cookie header, persisting if refreshed."""
        auth_file = self._auth_file("google")
        payload = {}
        if auth_file.exists():
            try:
                payload = json.loads(auth_file.read_text())
            except Exception:
                payload = {}

        env_token = os.environ.get("NOTEBOOKLM_AUTH_TOKEN")
        env_cookies = os.environ.get("NOTEBOOKLM_COOKIES")
        if env_token and env_cookies:
            payload["notebooklm_auth_token"] = env_token
            payload["notebooklm_cookies"] = env_cookies
            payload["notebooklm_updated_at"] = datetime.now(timezone.utc).isoformat()
            auth_file.parent.mkdir(parents=True, exist_ok=True)
            auth_file.write_text(json.dumps(payload))
            return {"auth_token": env_token, "cookies": env_cookies}

        token = payload.get("notebooklm_auth_token")
        cookies = payload.get("notebooklm_cookies")
        if token and cookies and not force_refresh:
            return {"auth_token": token, "cookies": cookies}

        extracted = None
        owns_client = False
        if client is None:
            client = AgentBrowserClient(session_id=self._load_session_id() or DEFAULT_SESSION_ID)
            client.connect()
            owns_client = True

        try:
            extracted = self._extract_notebooklm_credentials(client)
        except Exception:
            extracted = None
        finally:
            if owns_client:
                client.disconnect()

        if extracted:
            token, cookies = extracted
            payload["notebooklm_auth_token"] = token
            payload["notebooklm_cookies"] = cookies
            payload["notebooklm_updated_at"] = datetime.now(timezone.utc).isoformat()
            auth_file.parent.mkdir(parents=True, exist_ok=True)
            auth_file.write_text(json.dumps(payload))
            return {"auth_token": token, "cookies": cookies}

        if self.setup(service="google"):
            try:
                payload = json.loads(auth_file.read_text())
            except Exception:
                payload = {}
            token = payload.get("notebooklm_auth_token")
            cookies = payload.get("notebooklm_cookies")
            if token and cookies:
                return {"auth_token": token, "cookies": cookies}

        raise RuntimeError(
            "NotebookLM auth token or cookies unavailable. "
            "Run: python scripts/run.py auth_manager.py setup"
        )

    @staticmethod
    def _build_cookie_header(cookies: list) -> str:
        pairs = []
        for cookie in cookies or []:
            name = cookie.get("name")
            value = cookie.get("value")
            if name is None or value is None:
                continue
            pairs.append(f"{name}={value}")
        return "; ".join(pairs)

    def _extract_notebooklm_credentials(self, client: AgentBrowserClient):
        login_url = self._get_service_config("google")["login_url"]
        try:
            client.navigate(login_url)
        except Exception:
            pass

        token = client.evaluate("window.WIZ_global_data?.SNlM0e")
        cookie_list = client.get_cookies(login_url)
        cookie_header = self._build_cookie_header(cookie_list)
        if not token or not cookie_header:
            return None
        return token, cookie_header

    def validate(self, service: str = "google") -> bool:
        """Validate current authentication is still valid"""
        print("🔍 Validating authentication...")

        session_id = self._load_session_id()
        if not session_id:
            print("❌ No saved session")
            return False

        client = AgentBrowserClient(session_id=session_id)

        try:
            client.connect()
            self.restore_auth(service, client=client)
            client.navigate(self._get_service_config(service)["login_url"])
            time.sleep(2)

            snapshot = client.snapshot()

            if self._snapshot_indicates_auth(service, snapshot, client):
                print("✅ Authentication valid")
                self.save_auth(service, client=client)
                return True

            print("❌ Authentication expired")
            return False

        except AgentBrowserError as e:
            print(f"⚠️ Validation error: {e.message}")
            return False
        finally:
            client.disconnect()

    def clear(self, service: str = None):
        """Clear authentication data"""
        print("🧹 Clearing authentication data...")

        if service:
            auth_file = self._auth_file(service)
            if auth_file.exists():
                auth_file.unlink()
                print(f"   ✓ Removed {auth_file.name}")
        else:
            for config in self.SERVICES.values():
                auth_file = config["file"]
                if auth_file.exists():
                    auth_file.unlink()
                    print(f"   ✓ Removed {auth_file.name}")

            if AGENT_BROWSER_SESSION_FILE.exists():
                AGENT_BROWSER_SESSION_FILE.unlink()
                print("   ✓ Removed session_id")

        print("✅ Authentication data cleared")
        print("   Note: Browser profile preserved. Run 'reauth' for full reset.")

    def status(self, service: str = None):
        """Show current authentication status"""
        print("🔐 Authentication Status")
        print("=" * 40)

        services = [service] if service else list(self.SERVICES.keys())
        for service_name in services:
            info = self.get_auth_info(service_name)
            print(f"Service: {service_name}")
            if info.get("authenticated"):
                print("   Status: ✅ Authenticated")
                print(f"   Since: {info.get('timestamp', 'Unknown')}")
            else:
                print("   Status: ❌ Not authenticated")
                print(f"   Run: python scripts/run.py auth_manager.py setup --service {service_name}")

        session_id = self._load_session_id()
        if session_id:
            print(f"   Session: {session_id}")

    def watchdog_status(self):
        """Show watchdog and daemon status"""
        status = get_watchdog_status()
        print("🧭 Watchdog Status")
        print("=" * 40)
        print(f"   Daemon running: {'✅' if status['daemon_running'] else '❌'}")
        print(f"   Watchdog PID: {status['watchdog_pid'] or 'None'}")
        print(f"   Watchdog alive: {'✅' if status['watchdog_alive'] else '❌'}")
        print(f"   Owner PID: {status['owner_pid'] or 'None'}")
        print(f"   Owner alive: {'✅' if status['owner_alive'] else '❌'}")
        if status["idle_seconds"] is not None:
            idle = int(status["idle_seconds"])
            timeout = int(status["idle_timeout_seconds"])
            remaining = max(0, timeout - idle)
            print(f"   Idle seconds: {idle}")
            print(f"   Idle timeout: {timeout}")
            print(f"   Time remaining: {remaining}")
        else:
            print("   Idle seconds: Unknown")

    def stop_daemon(self) -> bool:
        """Stop the agent-browser daemon for the saved session"""
        session_id = self._load_session_id() or DEFAULT_SESSION_ID
        client = AgentBrowserClient(session_id=session_id)
        stopped = client.shutdown()
        if stopped:
            print("✅ Daemon stopped")
        else:
            print("ℹ️ No daemon running")
        return stopped


def main():
    parser = argparse.ArgumentParser(description='Manage NotebookLM authentication')
    parser.add_argument('command', choices=['setup', 'status', 'validate', 'reauth', 'clear', 'stop-daemon', 'watchdog-status'],
                       help='Command to run')
    parser.add_argument('--service', choices=list(AuthManager.SERVICES.keys()),
                        help='Auth service (default: google)')

    args = parser.parse_args()
    auth = AuthManager()

    if args.command == 'setup':
        success = auth.setup(service=args.service)
        sys.exit(0 if success else 1)
    elif args.command == 'status':
        auth.status(service=args.service)
    elif args.command == 'validate':
        success = auth.validate(service=args.service or "google")
        sys.exit(0 if success else 1)
    elif args.command == 'reauth':
        service = args.service or "google"
        auth.clear(service=None if args.service is None else service)
        success = auth.setup(service=service)
        sys.exit(0 if success else 1)
    elif args.command == 'clear':
        auth.clear(service=args.service)
    elif args.command == 'stop-daemon':
        success = auth.stop_daemon()
        sys.exit(0 if success else 1)
    elif args.command == 'watchdog-status':
        auth.watchdog_status()


if __name__ == "__main__":
    main()
