import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.auth_manager as auth_manager


class DummyClient:
    def __init__(self, state=None):
        self.state = state or {}
        self.saved_state = None
        self.session_id = "test-session"

    def get_storage_state(self):
        return self.state

    def set_storage_state(self, state):
        self.saved_state = state
        return True


class AuthManagerServiceTests(unittest.TestCase):
    def test_is_authenticated_checks_state_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            google_file = Path(tmpdir) / "google.json"
            zlib_file = Path(tmpdir) / "zlib.json"
            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"]
                },
                "zlibrary": {
                    "file": zlib_file,
                    "login_url": "https://zh.zlib.li/",
                    "success_indicators": ["logout"]
                }
            }

            google_file.write_text(json.dumps({"cookies": [{"name": "sid"}]}))

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                self.assertTrue(auth.is_authenticated("google"))
                self.assertFalse(auth.is_authenticated("zlibrary"))

    def test_restore_auth_loads_state_into_client(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            google_file = Path(tmpdir) / "google.json"
            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"]
                }
            }
            payload = {"cookies": [{"name": "sid"}], "origins": []}
            google_file.write_text(json.dumps(payload))

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                client = DummyClient()
                result = auth.restore_auth("google", client=client)

            self.assertTrue(result)
            self.assertEqual(client.saved_state, payload)

    def test_save_auth_writes_state_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            google_file = Path(tmpdir) / "google.json"
            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"]
                }
            }
            payload = {"cookies": [{"name": "sid"}], "origins": []}

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                client = DummyClient(state=payload)
                result = auth.save_auth("google", client=client)

            self.assertTrue(result)
            self.assertEqual(json.loads(google_file.read_text()), payload)

    def test_snapshot_indicates_auth_uses_google_check(self):
        auth = auth_manager.AuthManager()

        class FakeClient:
            def check_auth(self, snapshot):
                return True

        snapshot = "notebooklm"
        self.assertFalse(auth._snapshot_indicates_auth("google", snapshot, FakeClient()))
        self.assertFalse(auth._snapshot_indicates_auth(None, snapshot, FakeClient()))


if __name__ == "__main__":
    unittest.main()
