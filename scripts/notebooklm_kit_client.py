#!/usr/bin/env python3
"""
NotebookLM Kit client wrapper.
Invokes the notebooklm-kit Node bridge with stored credentials.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from auth_manager import AuthManager
from config import SKILL_DIR


class NotebookLMKitError(RuntimeError):
    """Raised when notebooklm-kit bridge calls fail."""


class NotebookLMKitClient:
    """Wrapper around the notebooklm-kit Node bridge script."""

    def __init__(
        self,
        auth_provider: AuthManager,
        runner: Optional[object] = None,
        node_path: str = "node",
        script_path: Optional[Path] = None,
    ):
        self.auth_provider = auth_provider
        self.runner = runner or subprocess.run
        self.node_path = node_path
        self.script_path = script_path or (SKILL_DIR / "scripts" / "notebooklm_kit_bridge.mjs")

    def create_notebook(self, title: str, emoji: Optional[str] = None) -> dict:
        """Create a notebook and return {id, title}."""
        args = ["create-notebook", "--title", title]
        if emoji:
            args += ["--emoji", emoji]
        payload = self._run(args)
        notebook_id = payload.get("notebookId") or payload.get("id")
        if not notebook_id:
            raise NotebookLMKitError("Notebook ID missing from notebooklm-kit response")
        return {"id": notebook_id, "title": payload.get("title", title)}

    def add_file(self, notebook_id: str, file_path: Path) -> dict:
        """Upload a file and return {source_ids, was_chunked, chunks}."""
        payload = self._run([
            "add-file",
            "--notebook-id",
            notebook_id,
            "--file",
            str(file_path),
        ])
        source_ids = []
        if "sourceId" in payload:
            source_ids = [payload["sourceId"]]
        elif "sourceIds" in payload:
            source_ids = payload["sourceIds"] or []
        elif "allSourceIds" in payload:
            source_ids = payload["allSourceIds"] or []
        if not source_ids:
            raise NotebookLMKitError("Source IDs missing from notebooklm-kit response")
        return {
            "source_ids": source_ids,
            "was_chunked": bool(payload.get("wasChunked")),
            "chunks": payload.get("chunks"),
        }

    def _run(self, args: list[str]) -> dict:
        return self._run_with_retry(args, force_refresh=False)

    def _run_with_retry(self, args: list[str], force_refresh: bool) -> dict:
        credentials = self.auth_provider.get_notebooklm_credentials(force_refresh=force_refresh)
        env = os.environ.copy()
        env["NOTEBOOKLM_AUTH_TOKEN"] = credentials["auth_token"]
        env["NOTEBOOKLM_COOKIES"] = credentials["cookies"]
        env.setdefault("NOTEBOOKLM_DEBUG", "false")

        if not self.script_path.exists():
            raise NotebookLMKitError(f"Bridge script missing: {self.script_path}")

        cmd = [self.node_path, str(self.script_path)] + args
        result = self.runner(
            cmd,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            message = stderr or stdout or "NotebookLM kit bridge failed"
            if not force_refresh and self._is_auth_error(message):
                return self._run_with_retry(args, force_refresh=True)
            raise NotebookLMKitError(message)

        output = result.stdout.strip()
        if not output:
            raise NotebookLMKitError("NotebookLM kit bridge returned empty output")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise NotebookLMKitError(f"Invalid JSON from notebooklm-kit bridge: {exc}") from exc

        if not isinstance(payload, dict):
            raise NotebookLMKitError("NotebookLM kit bridge returned unexpected payload")
        if payload.get("success") is False:
            error_message = payload.get("error", "NotebookLM kit bridge error")
            if not force_refresh and self._is_auth_error(error_message):
                return self._run_with_retry(args, force_refresh=True)
            raise NotebookLMKitError(error_message)
        return payload

    @staticmethod
    def _is_auth_error(message: str) -> bool:
        if not message:
            return False
        message_lower = message.lower()
        return any(token in message_lower for token in ("401", "403", "unauthorized", "not authenticated"))
