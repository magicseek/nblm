#!/usr/bin/env python3
"""
NotebookLM Wrapper - Thin async wrapper over notebooklm-py.
Handles auth loading, token refresh, and browser fallback for uploads.
"""

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any, List

from notebooklm import NotebookLMClient, AuthTokens

from config import (
    GOOGLE_AUTH_FILE,
    NOTEBOOKLM_TOKEN_STALENESS_DAYS,
    DEFAULT_SESSION_ID,
)


class NotebookLMError(Exception):
    """Base exception for NotebookLM wrapper errors."""

    def __init__(self, message: str, code: str = "UNKNOWN", recovery: str = ""):
        self.message = message
        self.code = code
        self.recovery = recovery
        super().__init__(message)


class NotebookLMAuthError(NotebookLMError):
    """Raised when authentication fails or tokens are invalid."""

    def __init__(self, message: str, recovery: str = ""):
        super().__init__(
            message,
            code="AUTH_ERROR",
            recovery=recovery or "Run: python scripts/run.py auth_manager.py setup",
        )


class NotebookLMWrapper:
    """Thin async wrapper over notebooklm-py with auth loading and fallback."""

    def __init__(self, auth_file: Optional[Path] = None):
        self.auth_file = auth_file or GOOGLE_AUTH_FILE
        self._client: Optional[NotebookLMClient] = None
        self._auth_data: Optional[dict] = None

    async def __aenter__(self) -> "NotebookLMWrapper":
        """Load auth and initialize notebooklm-py client."""
        self._auth_data = self._load_auth_file()
        auth_tokens = self._create_auth_tokens(self._auth_data)
        self._client = NotebookLMClient(auth_tokens)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up client resources."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    def _load_auth_file(self) -> dict:
        """Load auth data from file."""
        if not self.auth_file.exists():
            raise NotebookLMAuthError(
                "Auth file not found",
                recovery="Run: python scripts/run.py auth_manager.py setup",
            )
        try:
            return json.loads(self.auth_file.read_text())
        except json.JSONDecodeError as e:
            raise NotebookLMAuthError(f"Invalid auth file: {e}")

    def _create_auth_tokens(self, auth_data: dict) -> AuthTokens:
        """Create AuthTokens from stored auth data."""
        cookies = auth_data.get("cookies", [])
        csrf_token = auth_data.get("csrf_token")
        session_id = auth_data.get("session_id")

        if not cookies:
            raise NotebookLMAuthError("No cookies in auth file")
        if not csrf_token or not session_id:
            raise NotebookLMAuthError(
                "Missing csrf_token or session_id in auth file",
                recovery="Run: python scripts/run.py auth_manager.py reauth",
            )

        # Convert cookies list to dict format expected by notebooklm-py
        cookies_dict = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}

        return AuthTokens(
            cookies=cookies_dict,
            csrf_token=csrf_token,
            session_id=session_id,
        )

    def _is_token_stale(self) -> bool:
        """Check if tokens are older than staleness threshold."""
        if not self._auth_data:
            return True
        extracted_at = self._auth_data.get("extracted_at")
        if not extracted_at:
            return True
        try:
            timestamp = datetime.fromisoformat(extracted_at.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - timestamp
            return age > timedelta(days=NOTEBOOKLM_TOKEN_STALENESS_DAYS)
        except (ValueError, TypeError):
            return True

    @staticmethod
    def _is_auth_error(error: Exception) -> bool:
        """Check if an exception indicates an auth error."""
        message = str(error).lower()
        return any(
            token in message
            for token in ("401", "403", "unauthorized", "not authenticated", "invalid token")
        )
