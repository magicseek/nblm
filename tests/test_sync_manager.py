import json
import tempfile
import unittest
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.sync_manager import SyncManager, SyncState, SyncAction, TrackedFile, SUPPORTED_EXTENSIONS


class SyncManagerTests(unittest.TestCase):
    """Tests for SyncManager class."""

    def test_sync_state_creation(self):
        """Test that SyncState has correct defaults."""
        state = SyncState(folder_path="/test/path")
        self.assertEqual(state.version, 1)
        self.assertEqual(state.folder_path, "/test/path")
        self.assertIsNone(state.notebook_id)
        self.assertIsNone(state.account_index)
        self.assertEqual(state.files, {})

    def test_tracked_file_creation(self):
        """Test TrackedFile dataclass."""
        tf = TrackedFile(
            filename="test.md",
            hash="sha256:abc123",
            modified_at="2026-01-30T10:00:00Z",
            source_id="src-123",
            uploaded_at="2026-01-30T10:00:01Z"
        )
        self.assertEqual(tf.filename, "test.md")
        self.assertEqual(tf.hash, "sha256:abc123")
        self.assertEqual(tf.source_id, "src-123")

    def test_supported_extensions(self):
        """Test that all expected extensions are supported."""
        expected = {'.pdf', '.txt', '.md', '.docx', '.html', '.epub'}
        self.assertEqual(SUPPORTED_EXTENSIONS, expected)

    def test_sync_action_enum(self):
        """Test SyncAction enum values."""
        self.assertEqual(SyncAction.ADD.value, "add")
        self.assertEqual(SyncAction.UPDATE.value, "update")
        self.assertEqual(SyncAction.SKIP.value, "skip")
        self.assertEqual(SyncAction.DELETE.value, "delete")


class SyncManagerFolderTests(unittest.TestCase):
    """Tests for SyncManager folder scanning and tracking file location."""

    def test_tracking_file_in_data_sync_dir(self):
        """Test that tracking file is stored in data/sync/, not in synced folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            tracking_path = Path(mgr.tracking_file)
            # Tracking file path should be absolute
            self.assertTrue(tracking_path.is_absolute())
            # Tracking file should be in the repository's data/sync directory, not in tmpdir
            repo_root = Path(__file__).resolve().parents[1]
            expected_sync_dir = repo_root / "data" / "sync"
            self.assertEqual(tracking_path.parent, expected_sync_dir)
            # Should NOT be in the synced folder
            self.assertNotIn(Path(tmpdir).resolve(), tracking_path.parents)

    def test_tracking_file_name_is_hash_based(self):
        """Test that tracking file uses hash-based filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            # Should be .sync.json extension
            self.assertTrue(mgr.tracking_file.name.endswith(".sync.json"))
            # Should contain folder path hash (12 chars before extension)
            # Format: "{hash}.sync.json" → split gives ["{hash}", "sync", "json"]
            name_parts = mgr.tracking_file.name.split(".")
            self.assertEqual(len(name_parts), 3)
            self.assertEqual(len(name_parts[0]), 12)  # MD5 hash prefix

    def test_different_folders_have_different_tracking_files(self):
        """Test that different folders get different tracking files."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                mgr1 = SyncManager(tmpdir1)
                mgr2 = SyncManager(tmpdir2)
                # Different paths should have different tracking files
                self.assertNotEqual(mgr1.tracking_file, mgr2.tracking_file)

    def test_same_path_resolves_to_same_tracking_file(self):
        """Test that the same path (with resolve()) gets the same tracking file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            path1 = base / "test" / "folder"
            path2 = base / "test" / ".." / "test" / "folder"
            # Ensure the target directory exists so resolve() behaves consistently
            path1.mkdir(parents=True, exist_ok=True)
            mgr1 = SyncManager(str(path1))
            mgr2 = SyncManager(str(path2.resolve()))
            # Both should resolve to the same path
            self.assertEqual(mgr1.folder_path, mgr2.folder_path)
            # And therefore have the same tracking file
            self.assertEqual(mgr1.tracking_file, mgr2.tracking_file)


class SyncManagerStateTests(unittest.TestCase):
    """Tests for sync state management."""

    def test_load_state_new_folder(self):
        """Test loading state when no tracking file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            result = mgr.load_state()
            # Should return True and create fresh state
            self.assertTrue(result)
            self.assertEqual(mgr.state.folder_path, str(Path(tmpdir).resolve()))
            self.assertEqual(len(mgr.state.files), 0)

    def test_save_and_load_state(self):
        """Test saving and loading state preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            mgr.state.notebook_id = "test-notebook-123"
            mgr.state.account_index = 1
            mgr.state.account_email = "test@example.com"
            mgr.state.files["test.md"] = TrackedFile(
                filename="test",
                hash="sha256:abc123",
                modified_at="2026-01-30T10:00:00Z",
                source_id="src-123"
            )
            
            # Save state
            self.assertTrue(mgr.save_state())
            self.assertTrue(mgr.tracking_file.exists())
            
            # Create new manager and load state
            mgr2 = SyncManager(tmpdir)
            self.assertTrue(mgr2.load_state())
            self.assertEqual(mgr2.state.notebook_id, "test-notebook-123")
            self.assertEqual(mgr2.state.account_index, 1)
            self.assertEqual(mgr2.state.account_email, "test@example.com")
            self.assertIn("test.md", mgr2.state.files)
            self.assertEqual(mgr2.state.files["test.md"].hash, "sha256:abc123")

    def test_load_state_corrupted_file(self):
        """Test loading state with corrupted tracking file creates fresh state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            # Write corrupted JSON
            mgr.tracking_file.write_text("{ this is not valid json }")
            
            result = mgr.load_state()
            # Should return True but create fresh state
            self.assertTrue(result)
            self.assertEqual(len(mgr.state.files), 0)

    def test_state_json_format(self):
        """Test that saved state has correct JSON structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            mgr.state.notebook_id = "nb-123"
            mgr.state.files["doc.md"] = TrackedFile(
                filename="doc",
                hash="sha256:def456",
                modified_at="2026-01-30T10:00:00Z",
                source_id="src-456",
                uploaded_at="2026-01-30T10:00:01Z"
            )
            mgr.save_state()
            
            # Verify JSON is valid and has expected structure
            data = json.loads(mgr.tracking_file.read_text())
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["notebook_id"], "nb-123")
            self.assertIn("doc.md", data["files"])
            self.assertEqual(data["files"]["doc.md"]["hash"], "sha256:def456")


class SyncManagerScanTests(unittest.TestCase):
    """Tests for folder scanning."""

    def test_scan_empty_folder(self):
        """Test scanning empty folder returns no files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            self.assertEqual(len(files), 0)

    def test_scan_finds_supported_files(self):
        """Test scanning finds all supported file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "test.pdf").write_text("pdf content")
            (Path(tmpdir) / "test.txt").write_text("txt content")
            (Path(tmpdir) / "test.md").write_text("markdown content")
            (Path(tmpdir) / "test.docx").write_text("docx content")
            (Path(tmpdir) / "test.html").write_text("html content")
            (Path(tmpdir) / "test.epub").write_text("epub content")
            
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            
            self.assertEqual(len(files), 6)

    def test_scan_ignores_unsupported_extensions(self):
        """Test scanning ignores unsupported file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("python content")
            (Path(tmpdir) / "test.json").write_text("json content")
            (Path(tmpdir) / "test.jpg").write_text("jpg content")
            
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            
            self.assertEqual(len(files), 0)

    def test_scan_ignores_hidden_files_and_folders(self):
        """Test scanning ignores hidden files and folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create hidden file
            (Path(tmpdir) / ".hidden.md").write_text("hidden content")
            # Create visible file
            (Path(tmpdir) / "visible.md").write_text("visible content")
            
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            
            # Only visible file should be found
            self.assertEqual(len(files), 1)
            self.assertNotIn(".hidden.md", files)
            self.assertIn("visible.md", files)

    def test_scan_nested_files(self):
        """Test scanning finds files in subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir" / "nested"
            subdir.mkdir(parents=True)
            (subdir / "nested.md").write_text("nested content")
            
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            
            self.assertEqual(len(files), 1)
            self.assertIn("subdir/nested/nested.md", files)

    def test_scan_file_info_structure(self):
        """Test that scanned file info has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("test content")
            
            mgr = SyncManager(tmpdir)
            files = mgr.scan_folder()
            
            self.assertIn("test.md", files)
            info = files["test.md"]
            self.assertEqual(info["path"], "test.md")
            self.assertEqual(info["filename"], "test")
            self.assertEqual(info["extension"], ".md")
            self.assertIn("modified_at", info)
            self.assertIn("size", info)


class SyncManagerHashTests(unittest.TestCase):
    """Tests for file hashing."""

    def test_compute_file_hash(self):
        """Test that file hash is computed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("hello world")
            
            mgr = SyncManager(tmpdir)
            hash_val = mgr.compute_file_hash(test_file)
            
            self.assertTrue(hash_val.startswith("sha256:"))
            # Verify hash is consistent
            hash_val2 = mgr.compute_file_hash(test_file)
            self.assertEqual(hash_val, hash_val2)

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "test1.md"
            file1.write_text("content A")
            file2 = Path(tmpdir) / "test2.md"
            file2.write_text("content B")
            
            mgr = SyncManager(tmpdir)
            hash1 = mgr.compute_file_hash(file1)
            hash2 = mgr.compute_file_hash(file2)
            
            self.assertNotEqual(hash1, hash2)

    def test_same_content_same_hash(self):
        """Test that same content produces same hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "test1.md"
            file1.write_text("same content")
            file2 = Path(tmpdir) / "test2.md"
            file2.write_text("same content")
            
            mgr = SyncManager(tmpdir)
            hash1 = mgr.compute_file_hash(file1)
            hash2 = mgr.compute_file_hash(file2)
            
            self.assertEqual(hash1, hash2)


class SyncManagerPlanTests(unittest.TestCase):
    """Tests for sync plan generation."""

    def test_plan_all_new_files(self):
        """Test that new files are marked for ADD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.md").write_text("content 1")
            (Path(tmpdir) / "file2.md").write_text("content 2")
            
            mgr = SyncManager(tmpdir)
            mgr.load_state()
            files = mgr.scan_folder()
            plan = mgr.get_sync_plan(files)
            
            # All files should be ADD
            self.assertEqual(len(plan), 2)
            for item in plan:
                self.assertEqual(item["action"], SyncAction.ADD.value)

    def test_plan_skip_unchanged_files(self):
        """Test that unchanged files are marked for SKIP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("test content")

            mgr = SyncManager(tmpdir)
            mgr.load_state()
            files = mgr.scan_folder()
            plan = mgr.get_sync_plan(files)

            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0]["action"], SyncAction.ADD.value)

            # Simulate successful upload - update state with tracked file info
            path = plan[0]["path"]
            local_info = plan[0]["local_info"]
            mgr.state.files[path] = TrackedFile(
                filename=local_info["filename"],
                hash=local_info["hash"],
                modified_at=local_info["modified_at"],
            )

            mgr.save_state()
            mgr.load_state()

            files = mgr.scan_folder()
            plan2 = mgr.get_sync_plan(files)

            self.assertEqual(len(plan2), 1)
            self.assertEqual(plan2[0]["action"], SyncAction.SKIP.value)

    def test_plan_update_changed_files(self):
        """Test that changed files are marked for UPDATE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("original content")

            mgr = SyncManager(tmpdir)
            mgr.load_state()
            files = mgr.scan_folder()

            plan1 = mgr.get_sync_plan(files)
            self.assertEqual(plan1[0]["action"], SyncAction.ADD.value)

            # Simulate successful upload - update state with tracked file info
            path = plan1[0]["path"]
            local_info = plan1[0]["local_info"]
            mgr.state.files[path] = TrackedFile(
                filename=local_info["filename"],
                hash=local_info["hash"],
                modified_at=local_info["modified_at"],
                source_id="src-123",
            )
            mgr.save_state()

            test_file.write_text("modified content")

            mgr.load_state()
            files2 = mgr.scan_folder()
            plan2 = mgr.get_sync_plan(files2)

            self.assertEqual(len(plan2), 1)
            self.assertEqual(plan2[0]["action"], SyncAction.UPDATE.value)
            self.assertIsNotNone(plan2[0]["source_id"])

    def test_plan_delete_removed_files(self):
        """Test that removed files are marked for DELETE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("test content")

            mgr = SyncManager(tmpdir)
            mgr.load_state()
            files = mgr.scan_folder()
            plan1 = mgr.get_sync_plan(files)

            # First sync: ADD
            self.assertEqual(plan1[0]["action"], SyncAction.ADD.value)

            path = plan1[0]["path"]
            local_info = plan1[0]["local_info"]
            mgr.state.files[path] = TrackedFile(
                filename=local_info["filename"],
                hash=local_info["hash"],
                modified_at=local_info["modified_at"],
                source_id="src-123",
            )
            mgr.save_state()

            test_file.unlink()

            mgr.load_state()
            files2 = mgr.scan_folder()

            self.assertEqual(len(mgr.state.files), 1)
            self.assertEqual(len(files2), 0)

            plan3 = mgr.get_sync_plan(files2)
            self.assertEqual(len(plan3), 1)
            self.assertEqual(plan3[0]["action"], SyncAction.DELETE.value)


class SyncManagerPrintTests(unittest.TestCase):
    """Tests for sync plan output formatting."""

    def test_print_sync_plan(self):
        """Test that sync plan is printed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("test content")
            
            mgr = SyncManager(tmpdir)
            mgr.load_state()
            files = mgr.scan_folder()
            plan = mgr.get_sync_plan(files)
            
            # Should not raise exception
            mgr._print_sync_plan(plan)


if __name__ == "__main__":
    unittest.main()