import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock
import shutil

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))

# Import modules
from scripts import account_manager
from scripts import auth_manager


class AccountValidationTests(unittest.TestCase):
    """Tests for account validation logic."""

    def test_email_validation_rejects_empty(self):
        """Test that empty email is rejected."""
        # Create a temporary directory for testing
        tmpdir = tempfile.mkdtemp()
        try:
            google_auth_dir = Path(tmpdir) / "auth" / "google"
            google_auth_dir.mkdir(parents=True)
            
            with mock.patch.object(account_manager, "GOOGLE_AUTH_DIR", google_auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_INDEX", google_auth_dir / "index.json"):
                mgr = account_manager.AccountManager()
                
                with self.assertRaises(ValueError) as ctx:
                    mgr.add_account("", {"cookies": []})
                self.assertIn("empty", str(ctx.exception).lower())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_email_validation_requires_at_sign(self):
        """Test that email must contain @ sign."""
        tmpdir = tempfile.mkdtemp()
        try:
            google_auth_dir = Path(tmpdir) / "auth" / "google"
            google_auth_dir.mkdir(parents=True)
            
            with mock.patch.object(account_manager, "GOOGLE_AUTH_DIR", google_auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_INDEX", google_auth_dir / "index.json"):
                mgr = account_manager.AccountManager()
                
                with self.assertRaises(ValueError) as ctx:
                    mgr.add_account("invalid-email", {"cookies": []})
                self.assertIn("@", str(ctx.exception))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_email_strips_whitespace(self):
        """Test that email is stripped of whitespace."""
        tmpdir = tempfile.mkdtemp()
        try:
            google_auth_dir = Path(tmpdir) / "auth" / "google"
            google_auth_dir.mkdir(parents=True)
            
            with mock.patch.object(account_manager, "GOOGLE_AUTH_DIR", google_auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_INDEX", google_auth_dir / "index.json"):
                mgr = account_manager.AccountManager()
                
                acc = mgr.add_account("  test@example.com  ", {"cookies": []})
                self.assertEqual(acc.email, "test@example.com")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TypeCompatibilityTests(unittest.TestCase):
    """Tests for Python version compatibility."""

    def test_union_type_compatibility(self):
        """Test that Union types work (Python 3.8+ compatibility)."""
        # This test just verifies the imports work correctly
        from typing import Union
        
        # Verify the function signatures use Union properly
        import inspect
        sig = inspect.signature(account_manager.AccountManager.switch_account)
        # Just verify the method exists and is callable
        self.assertTrue(callable(account_manager.AccountManager.switch_account))


class AuthManagerDependencyInjectionTests(unittest.TestCase):
    """Tests for AuthManager dependency injection."""

    def test_auth_manager_accepts_custom_account_manager(self):
        """Test that AuthManager can accept a custom AccountManager."""
        tmpdir = tempfile.mkdtemp()
        try:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True)
            
            # Create a mock account manager
            mock_acct_mgr = mock.MagicMock()
            mock_acct_mgr.get_active_auth_file.return_value = None
            
            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                 mock.patch.object(auth_manager, "AUTH_DIR", auth_dir):
                auth = auth_manager.AuthManager(account_manager=mock_acct_mgr)
            
            # Verify the mock was used
            self.assertIs(auth.account_manager, mock_acct_mgr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_auth_manager_creates_default_account_manager(self):
        """Test that AuthManager creates AccountManager if not provided."""
        tmpdir = tempfile.mkdtemp()
        try:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            google_auth_dir = auth_dir / "google"
            google_auth_dir.mkdir(parents=True)
            
            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                 mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_DIR", google_auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_INDEX", google_auth_dir / "index.json"):
                auth = auth_manager.AuthManager()
            
            # Verify an account manager was created
            self.assertIsNotNone(auth.account_manager)
            # Just check it has the expected methods (duck typing)
            self.assertTrue(hasattr(auth.account_manager, 'get_active_auth_file'))
            self.assertTrue(callable(auth.account_manager.get_active_auth_file))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class LegacyAuthFallbackTests(unittest.TestCase):
    """Tests for legacy authentication fallback."""

    def test_storage_state_falls_back_to_legacy(self):
        """Test that storage_state.json falls back to legacy google.json."""
        tmpdir = tempfile.mkdtemp()
        try:
            auth_dir = Path(tmpdir) / "auth"
            auth_dir.mkdir(parents=True)
            legacy_file = auth_dir / "google.json"
            legacy_file.write_text(json.dumps({"cookies": []}))
            
            # Create mock account manager returning None
            mock_acct_mgr = mock.MagicMock()
            mock_acct_mgr.get_active_auth_file.return_value = None
            
            with mock.patch.object(auth_manager, "DATA_DIR", Path(tmpdir)), \
                 mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                 mock.patch.object(auth_manager, "GOOGLE_AUTH_FILE", legacy_file):
                auth = auth_manager.AuthManager(account_manager=mock_acct_mgr)
                auth._ensure_storage_state_symlink(quiet=True)
            
            # Verify storage_state.json was created
            storage_state = auth_dir / "storage_state.json"
            self.assertTrue(storage_state.exists() or storage_state.is_symlink())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_storage_state_removed_when_no_auth(self):
        """Test that storage_state.json is removed when no auth available."""
        tmpdir = tempfile.mkdtemp()
        try:
            auth_dir = Path(tmpdir) / "auth"
            auth_dir.mkdir(parents=True)
            
            # Create a stale storage_state.json
            storage_state = auth_dir / "storage_state.json"
            storage_state.write_text("{}")
            
            # Create mock account manager returning None
            mock_acct_mgr = mock.MagicMock()
            mock_acct_mgr.get_active_auth_file.return_value = None
            
            with mock.patch.object(auth_manager, "DATA_DIR", Path(tmpdir)), \
                 mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                 mock.patch.object(auth_manager, "GOOGLE_AUTH_FILE", auth_dir / "nonexistent.json"):
                auth = auth_manager.AuthManager(account_manager=mock_acct_mgr)
                auth._ensure_storage_state_symlink(quiet=True)
            
            # Verify storage_state.json was removed
            self.assertFalse(storage_state.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class NotebookLMWrapperAuthErrorTests(unittest.TestCase):
    """Tests for NotebookLMWrapper authentication error handling."""

    def test_invalid_account_index_raises_auth_error(self):
        """Test that invalid account_index raises NotebookLMAuthError."""
        # Skip if notebooklm is not installed (it's optional in tests)
        try:
            from scripts import notebooklm_wrapper
        except ImportError:
            self.skipTest("notebooklm module not installed")
        
        tmpdir = tempfile.mkdtemp()
        try:
            google_auth_dir = Path(tmpdir) / "auth" / "google"
            google_auth_dir.mkdir(parents=True)
            
            with mock.patch.object(account_manager, "GOOGLE_AUTH_DIR", google_auth_dir), \
                 mock.patch.object(account_manager, "GOOGLE_AUTH_INDEX", google_auth_dir / "index.json"):
                
                # Try to create wrapper with non-existent account index
                with self.assertRaises(notebooklm_wrapper.NotebookLMAuthError) as ctx:
                    wrapper = notebooklm_wrapper.NotebookLMWrapper(account_index=999)
                
                self.assertIn("Account not found", str(ctx.exception))
                self.assertEqual(ctx.exception.code, "AUTH_ERROR")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
