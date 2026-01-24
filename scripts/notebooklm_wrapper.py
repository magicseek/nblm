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

    async def _with_retry(self, coro_func, max_retries: int = 1):
        """Execute coroutine with token refresh retry on auth errors."""
        try:
            return await coro_func()
        except Exception as e:
            if self._is_auth_error(e) and max_retries > 0:
                await self._refresh_tokens()
                return await self._with_retry(coro_func, max_retries - 1)
            raise NotebookLMError(str(e), code="API_ERROR")

    async def _refresh_tokens(self):
        """Refresh tokens using agent-browser."""
        # Import here to avoid circular dependency
        from auth_manager import AuthManager

        auth_manager = AuthManager()
        # This is synchronous but we call it from async context
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, auth_manager.refresh_notebooklm_tokens)

        # Reload auth data
        self._auth_data = self._load_auth_file()

        # Recreate client with fresh tokens
        if self._client:
            await self._client.__aexit__(None, None, None)
        auth_tokens = self._create_auth_tokens(self._auth_data)
        self._client = NotebookLMClient(auth_tokens)
        await self._client.__aenter__()

    # === Notebooks API ===

    async def create_notebook(self, name: str) -> dict:
        """Create a new notebook. Falls back to browser on failure."""
        async def _create():
            notebook = await self._client.notebooks.create(name)
            return {
                "id": notebook.id,
                "title": notebook.title,
            }
        try:
            return await self._with_retry(_create)
        except NotebookLMError:
            # Fallback to browser creation
            return await self._fallback_create_notebook(name)

    async def list_notebooks(self) -> List[dict]:
        """List all notebooks."""
        async def _list():
            notebooks = await self._client.notebooks.list()
            return [
                {
                    "id": nb.id,
                    "title": nb.title,
                }
                for nb in notebooks
            ]
        return await self._with_retry(_list)

    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        async def _delete():
            await self._client.notebooks.delete(notebook_id)
            return True
        return await self._with_retry(_delete)

    # === Sources API ===

    async def add_file(self, notebook_id: str, file_path: Path) -> dict:
        """Upload a file to a notebook. Falls back to browser on failure."""
        async def _add():
            source = await self._client.sources.add_file(notebook_id, file_path)
            return {
                "source_id": source.id,
                "title": source.title,
                "source_type": source.source_type,
            }

        try:
            return await self._with_retry(_add)
        except NotebookLMError:
            # Fallback to browser upload
            return await self._fallback_upload(notebook_id, file_path)

    async def add_url(self, notebook_id: str, url: str) -> dict:
        """Add a URL source to a notebook."""
        async def _add():
            source = await self._client.sources.add_url(notebook_id, url)
            return {
                "source_id": source.id,
                "title": source.title,
                "source_type": source.source_type,
            }
        return await self._with_retry(_add)

    async def add_youtube(self, notebook_id: str, url: str) -> dict:
        """Add a YouTube video source to a notebook."""
        async def _add():
            source = await self._client.sources.add_youtube(notebook_id, url)
            return {
                "source_id": source.id,
                "title": source.title,
                "source_type": source.source_type,
            }
        return await self._with_retry(_add)

    async def add_text(self, notebook_id: str, title: str, content: str) -> dict:
        """Add text content as a source to a notebook."""
        async def _add():
            source = await self._client.sources.add_text(notebook_id, title, content)
            return {
                "source_id": source.id,
                "title": source.title,
                "source_type": source.source_type,
            }
        return await self._with_retry(_add)

    async def list_sources(self, notebook_id: str) -> List[dict]:
        """List all sources in a notebook."""
        async def _list():
            sources = await self._client.sources.list(notebook_id)
            return [
                {
                    "source_id": src.id,
                    "title": src.title,
                    "source_type": src.source_type,
                    "is_ready": src.is_ready,
                }
                for src in sources
            ]
        return await self._with_retry(_list)

    async def get_source(self, notebook_id: str, source_id: str) -> dict:
        """Get details of a specific source."""
        async def _get():
            source = await self._client.sources.get(notebook_id, source_id)
            return {
                "source_id": source.id,
                "title": source.title,
                "source_type": source.source_type,
                "is_ready": source.is_ready,
            }
        return await self._with_retry(_get)

    async def delete_source(self, notebook_id: str, source_id: str) -> bool:
        """Delete a source from a notebook."""
        async def _delete():
            await self._client.sources.delete(notebook_id, source_id)
            return True
        return await self._with_retry(_delete)

    # === Chat API ===

    async def chat(self, notebook_id: str, message: str) -> dict:
        """Send a chat message to a notebook and get a response."""
        async def _chat():
            response = await self._client.chat(notebook_id, message)
            return {
                "text": response.text,
                "citations": response.citations if hasattr(response, "citations") else [],
            }
        return await self._with_retry(_chat)

    # === Browser Fallback ===

    async def _fallback_create_notebook(self, name: str) -> dict:
        """Create notebook via browser automation when API fails."""
        from agent_browser_client import AgentBrowserClient, AgentBrowserError
        from auth_manager import AuthManager

        loop = asyncio.get_event_loop()

        def _browser_create():
            auth = AuthManager()
            client = AgentBrowserClient(session_id=DEFAULT_SESSION_ID)

            try:
                client.connect()
                auth.restore_auth("google", client=client)

                # Navigate to NotebookLM home
                print("   🌐 Creating notebook via browser...")
                client.navigate("https://notebooklm.google.com")

                import time
                time.sleep(3)

                # Get snapshot and find create notebook button
                snapshot = client.snapshot()
                create_ref = self._find_button_ref(snapshot, ["create", "new notebook", "new"])

                if not create_ref:
                    raise NotebookLMError(
                        "Create notebook button not found",
                        code="ELEMENT_NOT_FOUND",
                        recovery="Check if NotebookLM page loaded correctly",
                    )

                client.click(create_ref)
                time.sleep(2)

                # Get current URL to extract notebook ID
                snapshot = client.snapshot()
                # Look for notebook URL pattern in the page or get from navigation
                # The notebook ID appears in URL after creation

                # Wait for notebook to be created and page to update
                time.sleep(3)

                # Try to get the notebook ID from the URL
                current_url = client.evaluate("window.location.href")
                notebook_id = None
                if current_url and "notebook/" in current_url:
                    parts = current_url.split("notebook/")
                    if len(parts) > 1:
                        notebook_id = parts[1].split("/")[0].split("?")[0]

                if not notebook_id:
                    # Generate a placeholder - we'll get the real ID from the URL later
                    import uuid
                    notebook_id = str(uuid.uuid4())

                auth.save_auth("google", client=client)

                return {
                    "id": notebook_id,
                    "title": name,
                    "created_via": "browser_fallback",
                }

            except AgentBrowserError as e:
                raise NotebookLMError(e.message, code=e.code, recovery=e.recovery)
            finally:
                client.disconnect()

        return await loop.run_in_executor(None, _browser_create)

    async def _fallback_upload(self, notebook_id: str, file_path: Path) -> dict:
        """Upload file via browser automation when API fails."""
        from agent_browser_client import AgentBrowserClient, AgentBrowserError
        from auth_manager import AuthManager

        loop = asyncio.get_event_loop()

        def _browser_upload():
            auth = AuthManager()
            client = AgentBrowserClient(session_id=DEFAULT_SESSION_ID)

            try:
                client.connect()
                auth.restore_auth("google", client=client)

                # Navigate to notebook
                notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
                print(f"   🌐 Navigating to notebook for upload...")
                client.navigate(notebook_url)

                # Wait for page load
                import time
                time.sleep(3)

                # Get snapshot and find add source button
                snapshot = client.snapshot()
                add_ref = self._find_button_ref(snapshot, ["add source", "add sources", "add"])

                if not add_ref:
                    raise NotebookLMError(
                        "Add source button not found",
                        code="ELEMENT_NOT_FOUND",
                        recovery="Check if notebook page loaded correctly",
                    )

                print(f"   📎 Clicking add source button...")
                client.click(add_ref)
                time.sleep(2)

                # Get new snapshot and find upload/file option
                snapshot = client.snapshot()
                upload_ref = self._find_button_ref(snapshot, ["upload", "file", "pdf", "document"])

                if upload_ref:
                    client.click(upload_ref)
                    time.sleep(1)
                    snapshot = client.snapshot()

                # Find file input ref in snapshot
                file_input_ref = self._find_file_input_ref(snapshot)

                if not file_input_ref:
                    raise NotebookLMError(
                        "File input not found",
                        code="ELEMENT_NOT_FOUND",
                        recovery="Retry after page loads completely",
                    )

                # Upload file using agent-browser upload command with ref
                print(f"   📤 Uploading {file_path.name}...")
                client.upload(file_input_ref, [str(file_path)])

                # Wait for upload to process
                print(f"   ⏳ Waiting for upload to complete...")
                time.sleep(10)

                auth.save_auth("google", client=client)

                return {
                    "source_id": None,  # Unknown from browser upload
                    "title": file_path.name,
                    "uploaded_via": "browser_fallback",
                }

            except AgentBrowserError as e:
                raise NotebookLMError(e.message, code=e.code, recovery=e.recovery)
            finally:
                client.disconnect()

        return await loop.run_in_executor(None, _browser_upload)

    @staticmethod
    def _find_file_input_ref(snapshot: str) -> Optional[str]:
        """Find file input ref in snapshot."""
        for line in snapshot.splitlines():
            lower = line.lower()
            # Look for file input or upload-related elements
            if "file" in lower and ("input" in lower or "upload" in lower):
                match = re.search(r'\[ref=(\w+)\]', line)
                if match:
                    return match.group(1)
        # Fallback: look for any input that might be file-related
        for line in snapshot.splitlines():
            if "input" in line.lower() and "type" not in line.lower():
                match = re.search(r'\[ref=(\w+)\]', line)
                if match:
                    return match.group(1)
        return None

    @staticmethod
    def _find_button_ref(snapshot: str, keywords: List[str]) -> Optional[str]:
        """Find button ref in snapshot matching keywords."""
        for line in snapshot.splitlines():
            lower = line.lower()
            if "button" not in lower:
                continue
            if not any(keyword in lower for keyword in keywords):
                continue
            match = re.search(r'\[ref=(\w+)\]', line)
            if match:
                return match.group(1)
        return None