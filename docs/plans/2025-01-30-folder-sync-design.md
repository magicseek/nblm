# Folder Sync Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add folder sync capability to nblm that can scan a directory, detect new/modified/unchanged files, and sync them to a NotebookLM notebook with proper tracking.

**Architecture:** New `SyncManager` class in `scripts/sync_manager.py` that handles scanning, hashing, comparing, and syncing files. Tracking file `.nblm-sync.json` stored in the synced folder root records file hashes and source IDs. Command extends `source_manager.py` with `sync` subcommand.

**Tech Stack:** Python 3.10+, notebooklm-py for API operations, hashlib for SHA-256, json for tracking file, argparse for CLI.

---

## Prerequisites

Before starting implementation, verify these files exist and understand their structure:
- `scripts/source_manager.py` - Existing source upload logic (333 lines)
- `scripts/notebook_manager.py` - NotebookLibrary class for notebook operations
- `scripts/notebooklm_wrapper.py` - NotebookLMWrapper for API operations
- `scripts/config.py` - Configuration and paths

---

## Task 1: Create SyncManager Class Skeleton

**Files:**
- Create: `scripts/sync_manager.py`

**Step 1: Create the empty file with class skeleton**

```python
#!/usr/bin/env python3
"""
Folder sync manager for NotebookLM.
Scans local folders, tracks file changes, and syncs to NotebookLM notebooks.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
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
        """Load sync state from tracking file."""
        pass

    def save_state(self) -> bool:
        """Save sync state to tracking file."""
        pass

    def scan_folder(self) -> dict[str, dict]:
        """Scan folder for supported files."""
        pass

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        pass

    def get_sync_plan(self) -> list[dict]:
        """Generate sync plan comparing local files with tracking state."""
        pass

    async def execute_sync(self, notebook_id: str, dry_run: bool = False) -> dict:
        """Execute the sync plan."""
        pass
```

**Step 2: Commit**

```bash
git add docs/plans/2025-01-30-folder-sync-design.md
git commit -m "docs: add folder sync implementation plan"
```

---

## Task 2: Implement State Management (load_state, save_state)

**Files:**
- Modify: `scripts/sync_manager.py`

**Step 1: Write failing tests**

```python
# In tests/test_sync_manager.py
import pytest
from pathlib import Path
from sync_manager import SyncManager, SyncState, TrackedFile

def test_load_state_creates_new_if_not_exists(tmp_path):
    """Test that load_state creates new state if tracking file doesn't exist."""
    manager = SyncManager(str(tmp_path))
    result = manager.load_state()
    assert result is True
    assert manager.state.folder_path == str(tmp_path)
    assert manager.state.files == {}

def test_load_state_loads_existing(tmp_path):
    """Test that load_state loads existing tracking file."""
    tracking = tmp_path / ".nblm-sync.json"
    tracking.write_text(json.dumps({
        "version": 1,
        "folder_path": str(tmp_path),
        "notebook_id": "test-123",
        "files": {
            "test.md": {
                "filename": "test",
                "hash": "abc123",
                "modified_at": "2025-01-30T10:00:00Z"
            }
        }
    }))
    
    manager = SyncManager(str(tmp_path))
    result = manager.load_state()
    
    assert result is True
    assert manager.state.notebook_id == "test-123"
    assert "test.md" in manager.state.files

def test_save_state_writes_json(tmp_path):
    """Test that save_state writes tracking file."""
    manager = SyncManager(str(tmp_path))
    manager.state.notebook_id = "test-456"
    manager.state.files["doc.md"] = TrackedFile(
        filename="doc",
        hash="def456",
        modified_at="2025-01-30T11:00:00Z"
    )
    
    result = manager.save_state()
    
    assert result is True
    assert tracking.exists()
    data = json.loads(tracking.read_text())
    assert data["notebook_id"] == "test-456"
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/troy.huang/workspace/AgentSkills/nblm
python -m pytest tests/test_sync_manager.py -v
# Expected: FAIL (module not found, functions not defined)
```

**Step 3: Implement load_state and save_state**

```python
def load_state(self) -> bool:
    """Load sync state from tracking file."""
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
    """Save sync state to tracking file."""
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
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/troy.huang/workspace/AgentSkills/nblm
python -m pytest tests/test_sync_manager.py::test_load_state_creates_new_if_not_exists tests/test_sync_manager.py::test_load_state_loads_existing tests/test_sync_manager.py::test_save_state_writes_json -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add scripts/sync_manager.py tests/test_sync_manager.py
git commit -m "feat(sync): add SyncManager state management (load/save)"
```

---

## Task 3: Implement Folder Scanning and Hashing

**Files:**
- Modify: `scripts/sync_manager.py`

**Step 1: Write failing tests**

```python
def test_scan_folder_finds_supported_files(tmp_path):
    """Test that scan_folder finds all supported files."""
    (tmp_path / "doc1.md").write_text("# Doc 1")
    (tmp_path / "doc2.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "ignored.txt").write_text("ignored")  # .txt not supported
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "doc3.md").write_text("# Doc 3")
    
    manager = SyncManager(str(tmp_path))
    result = manager.scan_folder()
    
    assert "doc1.md" in result
    assert "doc2.pdf" in result
    assert "doc3.md" in result
    assert "ignored.txt" not in result

def test_compute_file_hash_is_deterministic(tmp_path):
    """Test that file hash is deterministic."""
    content = b"test content"
    (tmp_path / "test.md").write_bytes(content)
    
    manager = SyncManager(str(tmp_path))
    hash1 = manager.compute_file_hash(tmp_path / "test.md")
    hash2 = manager.compute_file_hash(tmp_path / "test.md")
    
    assert hash1 == hash2
    assert hash1.startswith("sha256:")

def test_compute_file_hash_differs_for_different_content(tmp_path):
    """Test that different content produces different hashes."""
    (tmp_path / "test1.md").write_text("content 1")
    (tmp_path / "test2.md").write_text("content 2")
    
    manager = SyncManager(str(tmp_path))
    hash1 = manager.compute_file_hash(tmp_path / "test1.md")
    hash2 = manager.compute_file_hash(tmp_path / "test2.md")
    
    assert hash1 != hash2
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sync_manager.py -v -k "scan_folder or compute_file_hash"
# Expected: FAIL (functions not defined)
```

**Step 3: Implement scan_folder and compute_file_hash**

```python
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
    files = {}
    
    if not self.folder_path.exists():
        print(f"⚠️ Folder does not exist: {self.folder_path}")
        return files
    
    for root, dirs, filenames in os.walk(self.folder_path):
        # Skip the tracking file itself and dotfiles
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in filenames:
            # Skip tracking file
            if filename == self.TRACKING_FILENAME:
                continue
            
            path = Path(root) / filename
            relative_path = path.relative_to(self.folder_path)
            
            # Check extension
            ext = path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            
            try:
                stat = path.stat()
                files[str(relative_path)] = {
                    "path": str(relative_path),
                    "absolute_path": str(path),
                    "filename": path.stem,
                    "extension": ext,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                }
            except OSError as e:
                print(f"⚠️ Could not access {path}: {e}")
    
    print(f"📁 Found {len(files)} supported files in {self.folder_path}")
    return files

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
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sync_manager.py -v -k "scan_folder or compute_file_hash"
# Expected: PASS
```

**Step 5: Commit**

```bash
git add scripts/sync_manager.py
git commit -m "feat(sync): add folder scanning and file hashing"
```

---

## Task 4: Implement Sync Plan Generation

**Files:**
- Modify: `scripts/sync_manager.py`

**Step 1: Write failing tests**

```python
def test_get_sync_plan_add_new_file(tmp_path):
    """Test that new files are marked for addition."""
    # No tracking file - all files should be new
    (tmp_path / "new.md").write_text("new content")
    
    manager = SyncManager(str(tmp_path))
    manager.load_state()
    local_files = manager.scan_folder()
    plan = manager.get_sync_plan(local_files)
    
    assert len(plan) == 1
    assert plan[0]["action"] == "add"
    assert plan[0]["path"] == "new.md"

def test_get_sync_plan_skip_unchanged(tmp_path):
    """Test that unchanged files are skipped."""
    # Create tracking file with existing file
    tracking = tmp_path / ".nblm-sync.json"
    tracking.write_text(json.dumps({
        "version": 1,
        "folder_path": str(tmp_path),
        "files": {
            "existing.md": {
                "filename": "existing",
                "hash": "sha256:abc123",  # Pre-set hash
                "modified_at": "2025-01-30T10:00:00Z"
            }
        }
    }))
    
    # Create file with same content (will hash to same value)
    content = b"same content"
    expected_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
    (tmp_path / "existing.md").write_bytes(content)
    
    manager = SyncManager(str(tmp_path))
    manager.load_state()
    local_files = manager.scan_folder()
    plan = manager.get_sync_plan(local_files)
    
    assert len(plan) == 1
    assert plan[0]["action"] == "skip"
    assert plan[0]["path"] == "existing.md"

def test_get_sync_plan_update_modified(tmp_path):
    """Test that modified files are marked for update."""
    tracking = tmp_path / ".nblm-sync.json"
    tracking.write_text(json.dumps({
        "version": 1,
        "folder_path": str(tmp_path),
        "files": {
            "modified.md": {
                "filename": "modified",
                "hash": "sha256:oldhash",
                "modified_at": "2025-01-30T10:00:00Z",
                "source_id": "source-123"
            }
        }
    }))
    
    # Create file with different content
    (tmp_path / "modified.md").write_text("new content")
    
    manager = SyncManager(str(tmp_path))
    manager.load_state()
    local_files = manager.scan_folder()
    plan = manager.get_sync_plan(local_files)
    
    assert len(plan) == 1
    assert plan[0]["action"] == "update"
    assert plan[0]["path"] == "modified.md"
    assert plan[0]["source_id"] == "source-123"  # Has existing source_id
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sync_manager.py -v -k "get_sync_plan"
# Expected: FAIL (function not defined)
```

**Step 3: Implement get_sync_plan**

```python
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
    plan = []
    
    # Check each local file
    for path, local_info in local_files.items():
        # Compute hash for comparison
        abs_path = Path(local_info["absolute_path"])
        current_hash = self.compute_file_hash(abs_path)
        local_info["hash"] = current_hash
        
        if path not in self.state.files:
            # New file - needs addition
            plan.append({
                "action": SyncAction.ADD.value,
                "path": path,
                "local_info": local_info,
                "tracked_info": None,
                "source_id": None,
            })
        else:
            tracked = self.state.files[path]
            
            if tracked.hash != current_hash:
                # Content changed - needs update
                if tracked.source_id:
                    plan.append({
                        "action": SyncAction.UPDATE.value,
                        "path": path,
                        "local_info": local_info,
                        "tracked_info": tracked,
                        "source_id": tracked.source_id,
                    })
                else:
                    # No existing source, treat as add
                    plan.append({
                        "action": SyncAction.ADD.value,
                        "path": path,
                        "local_info": local_info,
                        "tracked_info": tracked,
                        "source_id": None,
                    })
            else:
                # Unchanged - skip
                plan.append({
                    "action": SyncAction.SKIP.value,
                    "path": path,
                    "local_info": local_info,
                    "tracked_info": tracked,
                    "source_id": tracked.source_id,
                })
    
    # Check for deleted files (in tracking but not in local)
    for path in self.state.files:
        if path not in local_files:
            plan.append({
                "action": SyncAction.DELETE.value,
                "path": path,
                "local_info": None,
                "tracked_info": self.state.files[path],
                "source_id": self.state.files[path].source_id,
            })
    
    return plan
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sync_manager.py -v -k "get_sync_plan"
# Expected: PASS
```

**Step 5: Commit**

```bash
git add scripts/sync_manager.py
git commit -m "feat(sync): add sync plan generation"
```

---

## Task 5: Implement Sync Execution

**Files:**
- Modify: `scripts/sync_manager.py`
- Dependencies: notebooklm_wrapper.py, config.py

**Step 1: Write failing test (mock-based)**

```python
@pytest.mark.asyncio
async def test_execute_sync_adds_new_file(tmp_path):
    """Test that sync execution adds new files."""
    (tmp_path / "new.md").write_text("new content")
    
    manager = SyncManager(str(tmp_path))
    manager.load_state()
    local_files = manager.scan_folder()
    plan = manager.get_sync_plan(local_files)
    
    # Mock the wrapper
    mock_wrapper = AsyncMock()
    mock_wrapper.add_file.return_value = {"source_id": "new-source-123"}
    
    result = await manager._execute_plan(mock_wrapper, plan, "notebook-123", dry_run=True)
    
    assert result["add"] == 1
    assert mock_wrapper.add_file.called

@pytest.mark.asyncio
async def test_execute_sync_updates_modified(tmp_path):
    """Test that sync execution updates modified files."""
    tracking = tmp_path / ".nblm-sync.json"
    tracking.write_text(json.dumps({
        "version": 1,
        "folder_path": str(tmp_path),
        "files": {
            "modified.md": {
                "filename": "modified",
                "hash": "sha256:oldhash",
                "modified_at": "2025-01-30T10:00:00Z",
                "source_id": "old-source-123"
            }
        }
    }))
    
    (tmp_path / "modified.md").write_text("new content")
    
    manager = SyncManager(str(tmp_path))
    manager.load_state()
    local_files = manager.scan_folder()
    plan = manager.get_sync_plan(local_files)
    
    mock_wrapper = AsyncMock()
    mock_wrapper.delete_source.return_value = True
    mock_wrapper.add_file.return_value = {"source_id": "new-source-456"}
    
    result = await manager._execute_plan(mock_wrapper, plan, "notebook-123", dry_run=False)
    
    assert result["update"] == 1
    assert mock_wrapper.delete_source.called
    assert mock_wrapper.add_file.called
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sync_manager.py -v -k "execute_sync"
# Expected: FAIL (function not defined, missing mock)
```

**Step 3: Implement execute_sync methods**

```python
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
    from notebooklm_wrapper import NotebookLMWrapper
    
    # Load state
    self.load_state()
    
    # Validate account match
    if self.state.account_index is not None and self.state.account_index != account_index:
        print(f"⚠️ Tracking file was created with account [{self.state.account_index}] {self.state.account_email}")
        print(f"   Current active account: [{account_index}] {account_email}")
        print("   Continuing with new account (tracking file will be updated)")
    
    # Scan and plan
    local_files = self.scan_folder()
    plan = self.get_sync_plan(local_files)
    
    # Show plan
    self._print_sync_plan(plan, dry_run)
    
    if dry_run:
        return self._summarize_plan(plan)
    
    # Execute
    async with NotebookLMWrapper() as wrapper:
        result = await self._execute_plan(wrapper, plan, notebook_id)
    
    # Update state
    self.state.notebook_id = notebook_id
    self.state.account_index = account_index
    self.state.account_email = account_email
    self.state.last_sync_at = datetime.now(timezone.utc).isoformat()
    self.save_state()
    
    return result

async def _execute_plan(
    self,
    wrapper,
    plan: list[dict],
    notebook_id: str,
    dry_run: bool = False,
) -> dict:
    """Execute sync plan using NotebookLMWrapper."""
    result = {"add": 0, "update": 0, "skip": 0, "delete": 0, "errors": []}
    
    for item in plan:
        action = item["action"]
        path = item["path"]
        local_info = item["local_info"]
        
        if action == SyncAction.SKIP.value:
            result["skip"] += 1
            continue
        
        if dry_run:
            print(f"   [{'DRY-RUN' if dry_run else ''}] {action.upper()} {path}")
            continue
        
        try:
            if action == SyncAction.ADD.value:
                print(f"   ➕ Adding: {path}")
                file_path = Path(local_info["absolute_path"])
                upload_result = await wrapper.add_file(notebook_id, file_path)
                source_id = upload_result.get("source_id")
                
                # Update tracking
                self.state.files[path] = TrackedFile(
                    filename=local_info["filename"],
                    hash=local_info["hash"],
                    modified_at=local_info["modified_at"],
                    source_id=source_id,
                    uploaded_at=datetime.now(timezone.utc).isoformat(),
                )
                result["add"] += 1
            
            elif action == SyncAction.UPDATE.value:
                print(f"   🔄 Updating: {path}")
                old_source_id = item["source_id"]
                
                # Delete old
                if old_source_id:
                    await wrapper.delete_source(notebook_id, old_source_id)
                
                # Upload new
                file_path = Path(local_info["absolute_path"])
                upload_result = await wrapper.add_file(notebook_id, file_path)
                source_id = upload_result.get("source_id")
                
                # Update tracking
                self.state.files[path] = TrackedFile(
                    filename=local_info["filename"],
                    hash=local_info["hash"],
                    modified_at=local_info["modified_at"],
                    source_id=source_id,
                    uploaded_at=datetime.now(timezone.utc).isoformat(),
                )
                result["update"] += 1
            
            elif action == SyncAction.DELETE.value:
                print(f"   🗑️ Deleting remote: {path}")
                source_id = item["source_id"]
                if source_id:
                    await wrapper.delete_source(notebook_id, source_id)
                del self.state.files[path]
                result["delete"] += 1
        
        except Exception as e:
            print(f"   ❌ Error {action} {path}: {e}")
            result["errors"].append({"path": path, "action": action, "error": str(e)})
    
    return result

def _print_sync_plan(self, plan: list[dict], dry_run: bool = False):
    """Print formatted sync plan."""
    prefix = "🔍 [DRY-RUN] " if dry_run else "📋 Sync Plan:"
    print(f"\n{prefix}")
    
    counts = {"add": 0, "update": 0, "skip": 0, "delete": 0}
    for item in plan:
        action = item["action"]
        path = item["path"]
        counts[action] += 1
        symbol = {"add": "➕", "update": "🔄", "skip": "✓", "delete": "🗑️"}[action]
        print(f"   {symbol} {path:<30} [{action.upper()}]")
    
    print(f"\n   Total: {counts['add']} add, {counts['update']} update, {counts['skip']} skip, {counts['delete']} delete")

def _summarize_plan(self, plan: list[dict]) -> dict:
    """Summarize plan without executing."""
    result = {"add": 0, "update": 0, "skip": 0, "delete": 0, "errors": []}
    for item in plan:
        result[item["action"]] += 1
    return result
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sync_manager.py -v -k "execute_sync"
# Expected: PASS
```

**Step 5: Commit**

```bash
git add scripts/sync_manager.py
git commit -m "feat(sync): add sync execution logic"
```

---

## Task 6: Integrate with source_manager.py CLI

**Files:**
- Modify: `scripts/source_manager.py`

**Step 1: Write failing test**

```python
def test_sync_command_parses_arguments():
    """Test that sync command parses folder and options."""
    # This tests the CLI argument parsing
    pass  # CLI testing via integration test
```

**Step 2: Add sync command to source_manager.py**

Add to `async_main()`:

```python
# In async_main() parser setup:
parser.add_argument("command", choices=["add", "sync"], help="Command to run")
# ... existing add arguments ...

# New sync arguments (add after existing add arguments)
sync_parser = subparsers.add_parser("sync", help="Sync a folder to NotebookLM")
sync_parser.add_argument("folder", help="Folder path to sync")
sync_parser.add_argument("--use-active", action="store_true",
                         help="Sync to currently active notebook")
sync_parser.add_argument("--notebook-id", help="Existing notebook ID")
sync_parser.add_argument("--create-new", action="store_true",
                         help="Create a new notebook named after the folder")
sync_parser.add_argument("--dry-run", action="store_true",
                         help="Show sync plan without executing")
sync_parser.add_argument("--rebuild", action="store_true",
                         help="Force rebuild tracking file (re-hash all files)")
```

Add sync command handler:

```python
elif args.command == "sync":
    if not Path(args.folder).isdir():
        print(f"❌ Folder not found: {args.folder}", file=sys.stderr)
        raise SystemExit(1)
    
    # Resolve notebook target
    folder_name = Path(args.folder).stem
    notebook_id, create_new = _resolve_notebook_target(args, folder_name)
    
    # Get active account
    account_mgr = AccountManager()
    active = account_mgr.get_active_account()
    if not active:
        print("❌ No active Google account.", file=sys.stderr)
        print("   Run: python scripts/run.py auth_manager.py accounts list", file=sys.stderr)
        raise SystemExit(1)
    
    # Create manager and run sync
    manager = SyncManager(args.folder)
    
    # Rebuild option - delete tracking file
    if args.rebuild and manager.tracking_file.exists():
        manager.tracking_file.unlink()
        print(f"🗑️ Cleared tracking file for rebuild")
    
    result = await manager.execute_sync(
        notebook_id=notebook_id,
        account_index=active.index,
        account_email=active.email,
        dry_run=args.dry_run,
    )
    
    print(json.dumps(result, indent=2))
```

**Step 3: Add import at top of source_manager.py**

```python
from sync_manager import SyncManager
```

**Step 4: Test the CLI manually**

```bash
# Create test folder
mkdir -p /tmp/test-sync-folder
echo "# Test Doc" > /tmp/test-sync-folder/test.md

# Dry-run (should show plan without executing)
python scripts/run.py source_manager.py sync /tmp/test-sync-folder --dry-run
# Expected: Shows add plan

# Cleanup
rm -rf /tmp/test-sync-folder
```

**Step 5: Commit**

```bash
git add scripts/source_manager.py
git commit -m "feat(sync): add sync command to CLI"
```

---

## Task 7: Update SKILL.md Documentation

**Files:**
- Modify: `SKILL.md`

Add to the Source Management section:

```markdown
### Folder Sync
| Command | Description |
|---------|-------------|
| `upload <folder>` | Sync a folder of files to NotebookLM |
| `upload <folder> --dry-run` | Preview sync without executing |
| `upload <folder> --rebuild` | Force rebuild tracking file |

**Sync behavior:**
- New files → Uploaded
- Modified files → Old source deleted, new file uploaded
- Unchanged files → Skipped
- Files deleted locally → Remote source deleted

**Example:**
```bash
/nblm upload ./docs --dry-run           # Preview sync
/nblm upload ./docs --use-active        # Sync to active notebook
/nblm upload ./docs --create-new        # Create new notebook
/nblm upload ./docs --rebuild           # Rebuild tracking
```
```

**Step 2: Commit**

```bash
git add SKILL.md
git commit -m "docs: add folder sync documentation"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/test_folder_sync_integration.py` (if project has integration tests)

Or run manual integration tests:

```bash
# Setup test notebook
python scripts/run.py notebook_manager.py create "Sync Test"
python scripts/run.py notebook_manager.py list  # Note the notebook ID

# Create test folder with files
mkdir -p /tmp/nblm-test-sync
echo "# Document 1" > /tmp/nblm-test-sync/doc1.md
echo "# Document 2" > /tmp/nblm-test-sync/doc2.md

# Test 1: Dry-run
python scripts/run.py source_manager.py sync /tmp/nblm-test-sync --notebook-id <ID> --dry-run
# Expected: 2 add operations

# Test 2: Execute sync
python scripts/run.py source_manager.py sync /tmp/nblm-test-sync --notebook-id <ID>
# Expected: Files uploaded, tracking file created

# Test 3: Dry-run again (should show skip)
python scripts/run.py source_manager.py sync /tmp/nblm-test-sync --notebook-id <ID> --dry-run
# Expected: 0 add, 2 skip

# Test 4: Modify file and sync
echo "# Updated Document 1" > /tmp/nblm-test-sync/doc1.md
python scripts/run.py source_manager.py sync /tmp/nblm-test-sync --notebook-id <ID> --dry-run
# Expected: 1 update, 1 skip

# Cleanup
rm -rf /tmp/nblm-test-sync
```

---

## Summary

**Files created/modified:**
- `scripts/sync_manager.py` - New (400+ lines)
- `scripts/source_manager.py` - Modified (add sync command)
- `tests/test_sync_manager.py` - New (unit tests)
- `SKILL.md` - Modified (documentation)

**Commands:**
```bash
# Sync a folder
python scripts/run.py source_manager.py sync ./docs --use-active

# Preview without executing
python scripts/run.py source_manager.py sync ./docs --dry-run

# Force rebuild tracking
python scripts/run.py source_manager.py sync ./docs --rebuild
```

**Next steps after completing tasks:**
- Run full test suite
- Verify all commits are clean
- Test with real NotebookLM account

---

Plan complete and saved to `docs/plans/2025-01-30-folder-sync-design.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
