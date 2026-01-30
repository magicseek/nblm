#!/usr/bin/env python3
"""
Folder sync manager for NotebookLM.
Scans local folders, tracks file changes, and syncs to NotebookLM notebooks.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx', '.html', '.epub'}


class SyncAction(Enum):
    """Sync action types."""
    ADD = "add"
    UPDATE = "update"
    SKIP = "skip"
    DELETE = "delete"


@dataclass
class TrackedFile:
    """Represents a tracked file in the sync state."""
    filename: str
    hash: str
    modified_at: str
    source_id: Optional[str] = None
    uploaded_at: Optional[str] = None


@dataclass
class SyncState:
    """Represents the sync tracking state."""
    version: int = 1
    folder_path: str = ""
    notebook_id: Optional[str] = None
    notebook_url: Optional[str] = None
    account_index: Optional[int] = None
    account_email: Optional[str] = None
    last_sync_at: Optional[str] = None
    files: dict[str, TrackedFile] = field(default_factory=dict)


class SyncManager:
    """Manages folder-to-notebook synchronization."""

    TRACKING_FILENAME = ".nblm-sync.json"

    def __init__(self, folder_path: str):
        self.folder_path = Path(folder_path).resolve()
        self.tracking_file = self.folder_path / self.TRACKING_FILENAME
        self.state = SyncState(folder_path=str(self.folder_path))

    def load_state(self) -> bool:
        """Load sync state from tracking file.

        Returns:
            True if state loaded successfully (creates fresh state if file doesn't exist or is corrupted)
        """
        if not self.tracking_file.exists():
            # Create fresh state for new sync folder
            self.state = SyncState(folder_path=str(self.folder_path))
            return True

        try:
            data = json.loads(self.tracking_file.read_text())

            # Validate version
            if data.get("version") != 1:
                raise ValueError(f"Unsupported tracking file version: {data.get('version')}")

            # Reconstruct state
            self.state = SyncState(
                version=data.get("version", 1),
                folder_path=data.get("folder_path", str(self.folder_path)),
                notebook_id=data.get("notebook_id"),
                notebook_url=data.get("notebook_url"),
                account_index=data.get("account_index"),
                account_email=data.get("account_email"),
                last_sync_at=data.get("last_sync_at"),
            )

            # Reconstruct file entries
            for path, file_data in data.get("files", {}).items():
                self.state.files[path] = TrackedFile(
                    filename=file_data.get("filename", ""),
                    hash=file_data.get("hash", ""),
                    modified_at=file_data.get("modified_at", ""),
                    source_id=file_data.get("source_id"),
                    uploaded_at=file_data.get("uploaded_at"),
                )

            return True

        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️ Error loading tracking file: {e}")
            # Backup corrupted file
            broken = self.tracking_file.with_suffix(".json.broken")
            if not broken.exists():
                self.tracking_file.rename(broken)
                print(f"   Backed up corrupted file to: {broken}")
            # Create fresh state
            self.state = SyncState(folder_path=str(self.folder_path))
            return True

    def save_state(self) -> bool:
        """Save sync state to tracking file.

        Returns:
            True if saved successfully, False on error
        """
        try:
            data = {
                "version": self.state.version,
                "folder_path": self.state.folder_path,
                "notebook_id": self.state.notebook_id,
                "notebook_url": self.state.notebook_url,
                "account_index": self.state.account_index,
                "account_email": self.state.account_email,
                "last_sync_at": self.state.last_sync_at,
                "files": {}
            }

            for path, file_info in self.state.files.items():
                data["files"][path] = {
                    "filename": file_info.filename,
                    "hash": file_info.hash,
                    "modified_at": file_info.modified_at,
                    "source_id": file_info.source_id,
                    "uploaded_at": file_info.uploaded_at,
                }

            # Atomic write via temp file
            temp_file = self.tracking_file.with_suffix(".json.tmp")
            temp_file.write_text(json.dumps(data, indent=2))
            temp_file.rename(self.tracking_file)
            return True

        except Exception as e:
            print(f"❌ Error saving tracking file: {e}")
            return False

    def scan_folder(self) -> dict[str, dict]:
        """Scan folder for supported files.

        Returns:
            Dict mapping relative path -> file info dict with:
            - path: relative path from folder
            - absolute_path: full path
            - filename: file stem (without extension)
            - extension: file extension
            - modified_at: ISO timestamp
            - size: file size in bytes
        """
        return {}

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file.

        Returns:
            Hash string prefixed with algorithm name, e.g., "sha256:abc123..."
        """
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        return f"sha256:{sha256.hexdigest()}"

    def get_sync_plan(self, local_files: dict[str, dict]) -> list[dict]:
        """Generate sync plan comparing local files with tracking state.

        Args:
            local_files: Dict from scan_folder() with file info

        Returns:
            List of sync actions with:
            - action: SyncAction value
            - path: relative file path
            - local_info: file info from local_files
            - tracked_info: previous tracking info (if exists)
            - source_id: existing source ID for update/delete (if exists)
        """
        return []

    async def execute_sync(
        self,
        notebook_id: str,
        account_index: int,
        account_email: str,
        dry_run: bool = False,
    ) -> dict:
        """Execute full sync workflow.

        Args:
            notebook_id: Target NotebookLM notebook ID
            account_index: Active Google account index
            account_email: Active Google account email
            dry_run: If True, only show plan without executing

        Returns:
            Dict with sync results: add, update, skip, delete, errors
        """
        return {"add": 0, "update": 0, "skip": 0, "delete": 0, "errors": []}

    async def _execute_plan(
        self,
        wrapper,
        plan: list[dict],
        notebook_id: str,
        dry_run: bool = False,
    ) -> dict:
        """Execute sync plan using NotebookLMWrapper.

        Args:
            wrapper: NotebookLMWrapper instance
            plan: List of sync actions
            notebook_id: Target notebook ID
            dry_run: If True, don't actually modify anything

        Returns:
            Dict with sync results
        """
        return {"add": 0, "update": 0, "skip": 0, "delete": 0, "errors": []}

    def _print_sync_plan(self, plan: list[dict], dry_run: bool = False):
        """Print formatted sync plan.

        Args:
            plan: List of sync actions
            dry_run: If True, show dry-run indicator
        """
        pass

    def _summarize_plan(self, plan: list[dict]) -> dict:
        """Summarize plan without executing.

        Args:
            plan: List of sync actions

        Returns:
            Dict with counts by action type
        """
        return {"add": 0, "update": 0, "skip": 0, "delete": 0, "errors": []}