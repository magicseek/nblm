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
    def test_get_storage_state_reads_state_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            expected = {
                "cookies": [{"name": "sid", "value": "1"}],
                "origins": [
                    {
                        "origin": "https://example.com",
                        "localStorage": [{"name": "token", "value": "abc"}]
                    }
                ]
            }
            client = AgentBrowserClient(session_id="test")

            def fake_send(action, params=None):
                self.assertEqual(action, "state_save")
                self.assertEqual(Path(params["path"]), state_path)
                state_path.write_text(json.dumps(expected))
                return {}

            with mock.patch.object(client, "_send_command", side_effect=fake_send):
                result = client.get_storage_state(state_path=state_path)

            self.assertEqual(result, expected)

    def test_save_storage_state_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            payload = {
                "cookies": [{"name": "sid"}],
                "origins": []
            }
            client = AgentBrowserClient(session_id="test")

            with mock.patch.object(client, "get_storage_state", return_value=payload):
                result = client.save_storage_state(state_path)

            self.assertTrue(result)
            self.assertEqual(json.loads(state_path.read_text()), payload)

    def test_restore_storage_state_applies_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            payload = {
                "cookies": [{"name": "sid", "value": "1", "domain": "google.com", "path": "/"}],
                "origins": []
            }
            state_path.write_text(json.dumps(payload))

            client = AgentBrowserClient(session_id="test")
            with mock.patch.object(client, "set_storage_state") as set_state:
                result = client.restore_storage_state(state_path)

            self.assertTrue(result)
            set_state.assert_called_once_with(payload)

    def test_set_storage_state_applies_cookies_and_local_storage(self):
        payload = {
            "cookies": [{"name": "sid", "value": "1"}],
            "origins": [
                {
                    "origin": "https://example.com",
                    "localStorage": [{"name": "token", "value": "abc"}]
                }
            ]
        }
        client = AgentBrowserClient(session_id="test")
        with mock.patch.object(client, "_set_cookies") as set_cookies, \
            mock.patch.object(client, "navigate") as navigate, \
            mock.patch.object(client, "_send_command") as send_command:
            result = client.set_storage_state(payload)

        self.assertTrue(result)
        set_cookies.assert_called_once_with(payload["cookies"])
        navigate.assert_called_once_with("https://example.com")
        send_command.assert_called_once_with("storage_set", {
            "type": "local",
            "key": "token",
            "value": "abc"
        })


if __name__ == "__main__":
    unittest.main()
