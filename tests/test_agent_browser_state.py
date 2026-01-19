import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.agent_browser_client import AgentBrowserClient


class AgentBrowserStateTests(unittest.TestCase):
    def test_save_storage_state_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            client = AgentBrowserClient(session_id="test")

            with mock.patch.object(client, "_get_cookies", return_value=[{"name": "sid"}]), \
                mock.patch.object(client, "_get_local_storage", return_value={"token": "abc"}), \
                mock.patch.object(client, "_get_origin", return_value="https://notebooklm.google.com"):
                result = client.save_storage_state(state_path)

            self.assertTrue(result)
            payload = json.loads(state_path.read_text())
            self.assertEqual(payload["origin"], "https://notebooklm.google.com")
            self.assertEqual(payload["cookies"], [{"name": "sid"}])
            self.assertEqual(payload["local_storage"], {"token": "abc"})

    def test_restore_storage_state_applies_cookies_and_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            payload = {
                "origin": "https://notebooklm.google.com",
                "cookies": [{"name": "sid", "value": "1", "domain": "google.com", "path": "/"}],
                "local_storage": {"token": "abc"}
            }
            state_path.write_text(json.dumps(payload))

            client = AgentBrowserClient(session_id="test")
            with mock.patch.object(client, "navigate") as navigate, \
                mock.patch.object(client, "_set_cookies") as set_cookies, \
                mock.patch.object(client, "_set_local_storage") as set_storage:
                result = client.restore_storage_state(state_path)

            self.assertTrue(result)
            navigate.assert_called_once_with("https://notebooklm.google.com")
            set_cookies.assert_called_once_with(payload["cookies"])
            set_storage.assert_called_once_with(payload["local_storage"])


if __name__ == "__main__":
    unittest.main()
