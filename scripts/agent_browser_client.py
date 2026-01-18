#!/usr/bin/env python3
"""
Agent Browser Client for NotebookLM Skill
Python client that communicates with agent-browser daemon via Unix socket
"""

import json
import socket
import subprocess
import time
import re
import os
from pathlib import Path
from typing import Optional, Dict, Any

from config import (
    AGENT_BROWSER_PROFILE_DIR,
    AGENT_BROWSER_SESSION_FILE,
    AGENT_BROWSER_SOCKET_DIR,
    DEFAULT_SESSION_ID,
    SKILL_DIR
)


class AgentBrowserError(Exception):
    """Structured error for agent-browser operations"""

    def __init__(self, code: str, message: str, recovery: str, snapshot: str = None):
        self.code = code
        self.message = message
        self.recovery = recovery
        self.snapshot = snapshot
        super().__init__(f"[{code}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "recovery": self.recovery,
            "snapshot": self.snapshot
        }


class AgentBrowserClient:
    """Python client for agent-browser daemon"""

    def __init__(self, session_id: str = None):
        self.session_id = session_id or DEFAULT_SESSION_ID
        self.socket_path = AGENT_BROWSER_SOCKET_DIR / f"agent-browser-{self.session_id}.sock"
        self.user_data_dir = str(AGENT_BROWSER_PROFILE_DIR)
        self.socket: Optional[socket.socket] = None
        self._buffer = b""

        # Ensure directories exist
        AGENT_BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        AGENT_BROWSER_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> bool:
        """Connect to daemon, starting it if necessary"""
        if not self._daemon_is_running():
            self._start_daemon()

        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(str(self.socket_path))
            self.socket.settimeout(120)  # 2 minute timeout for long operations
            return True
        except ConnectionRefusedError:
            raise AgentBrowserError(
                code="DAEMON_UNAVAILABLE",
                message="Cannot connect to browser daemon",
                recovery="Check Node.js installation, ensure agent-browser is installed"
            )

    def disconnect(self):
        """Close connection to daemon"""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _daemon_is_running(self) -> bool:
        """Check if daemon socket exists and is responsive"""
        if not self.socket_path.exists():
            return False
        try:
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.connect(str(self.socket_path))
            test_socket.close()
            return True
        except Exception:
            return False

    def _start_daemon(self):
        """Start the agent-browser daemon"""
        print("🚀 Starting browser daemon...")

        env = os.environ.copy()
        env["AGENT_BROWSER_SESSION"] = self.session_id
        env["AGENT_BROWSER_USER_DATA_DIR"] = self.user_data_dir

        subprocess.Popen(
            ["npx", "agent-browser", "daemon"],
            cwd=str(SKILL_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for daemon to be ready
        for _ in range(30):  # 30 second timeout
            time.sleep(1)
            if self._daemon_is_running():
                print("✅ Daemon started")
                return

        raise AgentBrowserError(
            code="DAEMON_UNAVAILABLE",
            message="Daemon failed to start within timeout",
            recovery="Check Node.js and npm installation, run 'npm install' in skill directory"
        )

    def _send_command(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send command to daemon and receive response"""
        if not self.socket:
            raise AgentBrowserError(
                code="NOT_CONNECTED",
                message="Not connected to daemon",
                recovery="Call connect() first"
            )

        command = {"action": action}
        if params:
            command.update(params)

        # Send JSON terminated by newline
        message = json.dumps(command) + "\n"
        self.socket.sendall(message.encode())

        # Read response
        return self._read_response()

    def _read_response(self) -> Dict[str, Any]:
        """Read JSON response from daemon"""
        while True:
            # Check buffer for complete message
            if b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                return json.loads(line.decode())

            # Read more data
            try:
                chunk = self.socket.recv(65536)
                if not chunk:
                    raise AgentBrowserError(
                        code="CONNECTION_CLOSED",
                        message="Daemon closed connection",
                        recovery="Reconnect to daemon"
                    )
                self._buffer += chunk
            except socket.timeout:
                raise AgentBrowserError(
                    code="TIMEOUT",
                    message="Daemon response timeout",
                    recovery="Operation took too long, try again"
                )


if __name__ == "__main__":
    print("Agent Browser Client - Use with ask_question.py")
