#!/usr/bin/env python3
"""
Agent Browser Client for NotebookLM Skill
Python wrapper that drives the agent-browser CLI with a persistent session.
"""

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

from config import DEFAULT_SESSION_ID, SKILL_DIR


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
    """Python client for agent-browser CLI sessions"""

    def __init__(self, session_id: str = None, headed: bool = False):
        self.session_id = session_id or DEFAULT_SESSION_ID
        self.headed = headed
        self._cli_prefix = self._resolve_cli()
        self._headed_process: Optional[subprocess.Popen] = None
        self._last_url: Optional[str] = None

    def connect(self) -> bool:
        """Validate CLI availability"""
        if not self._cli_prefix:
            raise AgentBrowserError(
                code="CLI_UNAVAILABLE",
                message="agent-browser CLI not found",
                recovery="Run 'npm install' in the skill directory"
            )
        return True

    def disconnect(self):
        """Close the browser for this session"""
        self._stop_headed_process()
        try:
            self._run_command(["close"], expect_json=False, timeout=30)
        except Exception:
            pass

    def _resolve_cli(self) -> Optional[list]:
        """Resolve the agent-browser CLI path"""
        if os.name == "nt":
            local_cli = SKILL_DIR / "node_modules" / ".bin" / "agent-browser.cmd"
        else:
            local_cli = SKILL_DIR / "node_modules" / ".bin" / "agent-browser"

        if local_cli.exists():
            return [str(local_cli)]

        system_cli = shutil.which("agent-browser")
        if system_cli:
            return [system_cli]

        return None

    def _base_args(self) -> list:
        args = []
        if self.session_id:
            args.extend(["--session", self.session_id])
        if self.headed:
            args.append("--headed")
        return args

    def _start_headed_session(self, url: str):
        """Start a headed browser process that stays open for user login"""
        if self._headed_process and self._headed_process.poll() is None:
            return

        cmd = self._cli_prefix + ["open", url] + self._base_args()
        self._headed_process = subprocess.Popen(
            cmd,
            cwd=str(SKILL_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def _stop_headed_process(self):
        """Stop any background headed browser process"""
        if not self._headed_process:
            return
        if self._headed_process.poll() is None:
            try:
                self._headed_process.terminate()
                self._headed_process.wait(timeout=5)
            except Exception:
                self._headed_process.kill()
        self._headed_process = None

    def _parse_json_output(self, output: str) -> Dict[str, Any]:
        """Parse JSON output from agent-browser"""
        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        raise AgentBrowserError(
            code="CLI_ERROR",
            message="Failed to parse agent-browser output",
            recovery="Re-run command or enable --debug for details"
        )

    def _run_command(
        self,
        args: list,
        expect_json: bool = True,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Run an agent-browser CLI command"""
        if not self._cli_prefix:
            raise AgentBrowserError(
                code="CLI_UNAVAILABLE",
                message="agent-browser CLI not found",
                recovery="Run 'npm install' in the skill directory"
            )

        cmd = self._cli_prefix + args + self._base_args()
        if expect_json:
            cmd.append("--json")

        result = subprocess.run(
            cmd,
            cwd=str(SKILL_DIR),
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "agent-browser failed"
            raise AgentBrowserError(
                code="CLI_ERROR",
                message=message,
                recovery="Ensure agent-browser is installed and browsers are available"
            )

        if not expect_json:
            return {"stdout": result.stdout.strip()}

        payload = self._parse_json_output(result.stdout)
        if not payload.get("success", True):
            error = payload.get("error", "Unknown error")
            raise AgentBrowserError(
                code="CLI_ERROR",
                message=str(error),
                recovery="Retry the command or run with --debug"
            )

        return payload.get("data", payload)

    def _ref_arg(self, ref: str) -> str:
        return ref if ref.startswith("@") else f"@{ref}"

    # === Browser Actions ===

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL"""
        print(f"🌐 Navigating to {url[:50]}...")
        self._last_url = url
        if self.headed:
            self._start_headed_session(url)
            return {"url": url}
        return self._run_command(["open", url], expect_json=True)

    def snapshot(self, prune: bool = True) -> str:
        """Get accessibility tree snapshot of current page"""
        args = ["snapshot"]
        if prune:
            args.append("-c")
        for attempt in range(3):
            try:
                response = self._run_command(args, expect_json=True)
                return response.get("snapshot", "")
            except AgentBrowserError as exc:
                if "Browser not launched" in exc.message and self._last_url:
                    self._start_headed_session(self._last_url)
                    if attempt < 2:
                        time.sleep(2)
                        continue
                raise

    def click(self, ref: str) -> Dict[str, Any]:
        """Click element by ref"""
        print(f"🖱️ Clicking ref={ref}")
        return self._run_command(["click", self._ref_arg(ref)], expect_json=True)

    def fill(self, ref: str, text: str) -> Dict[str, Any]:
        """Fill input field by ref (clears first)"""
        print(f"⌨️ Filling ref={ref}")
        return self._run_command(["fill", self._ref_arg(ref), text], expect_json=True)

    def type_text(self, ref: str, text: str, submit: bool = False) -> Dict[str, Any]:
        """Type text into element (appends to existing)"""
        print(f"⌨️ Typing into ref={ref}")
        response = self._run_command(["type", self._ref_arg(ref), text], expect_json=True)
        if submit:
            self.press_key("Enter")
        return response

    def press_key(self, key: str) -> Dict[str, Any]:
        """Press keyboard key"""
        return self._run_command(["press", key], expect_json=True)

    def wait_for(self, text: str = None, timeout: int = 30) -> Dict[str, Any]:
        """Wait for text to appear on page"""
        if text:
            return self._run_command(["wait", "--text", text], expect_json=True, timeout=timeout + 5)
        return self._run_command(["wait", str(timeout * 1000)], expect_json=True, timeout=timeout + 5)

    # === Utility Methods ===

    def check_auth(self, snapshot: str = None) -> bool:
        """Check if current page indicates authentication is needed"""
        if snapshot is None:
            snapshot = self.snapshot()

        auth_indicators = [
            "accounts.google.com",
            "Sign in",
            "sign in",
            "Log in",
            "login"
        ]

        return any(indicator in snapshot for indicator in auth_indicators)

    def find_ref_by_role(self, snapshot: str, role: str, hint: str = None) -> Optional[str]:
        """Parse snapshot to find element ref by role and optional text hint"""
        for line in snapshot.split('\n'):
            line_lower = line.lower()
            if role.lower() in line_lower:
                if hint is None or hint.lower() in line_lower:
                    match = re.search(r'\[ref=(\w+)\]', line)
                    if match:
                        return match.group(1)
        return None

    def find_refs_by_role(self, snapshot: str, role: str) -> list:
        """Find all refs matching a role"""
        refs = []
        for line in snapshot.split('\n'):
            if role.lower() in line.lower():
                match = re.search(r'\[ref=(\w+)\]', line)
                if match:
                    refs.append(match.group(1))
        return refs


if __name__ == "__main__":
    print("Agent Browser Client - Use with ask_question.py")
