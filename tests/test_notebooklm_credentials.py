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
    def __init__(self):
        self.navigated = []
        self.evaluated = []
        self.restored = False

    def navigate(self, url: str, wait_until=None):
        self.navigated.append(url)

    def wait_for(self, timeout: int = 30):
        return True

    def evaluate(self, script: str):
        self.evaluated.append(script)
        return "token-xyz"

    def get_cookies(self, urls=None):
        return [
            {"name": "SID", "value": "abc"},
            {"name": "HSID", "value": "def"},
        ]

    def set_storage_state(self, state):
        self.restored = True
        return True


class NotebookLMCredentialsTests(unittest.TestCase):
    def test_get_notebooklm_credentials_persists_to_google_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps({"cookies": [], "origins": []}))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"]
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                client = DummyClient()
                result = auth.get_notebooklm_credentials(client=client)

            self.assertEqual(result["auth_token"], "token-xyz")
            self.assertEqual(result["cookies"], "SID=abc; HSID=def")

            saved = json.loads(google_file.read_text())
            self.assertEqual(saved["notebooklm_auth_token"], "token-xyz")
            self.assertEqual(saved["notebooklm_cookies"], "SID=abc; HSID=def")


if __name__ == "__main__":
    unittest.main()
