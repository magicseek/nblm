import unittest
from unittest import mock
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.agent_browser_client import AgentBrowserClient


class NavigateWaitUntilTests(unittest.TestCase):
    def test_cold_start_uses_domcontentloaded(self):
        client = AgentBrowserClient(session_id="test")
        client._started_daemon = True
        with mock.patch.object(client, "_send_command") as send:
            client.navigate("https://example.com")
        send.assert_called_once_with(
            "navigate",
            {"url": "https://example.com", "waitUntil": "domcontentloaded"}
        )

    def test_explicit_wait_until_overrides_cold_start(self):
        client = AgentBrowserClient(session_id="test")
        client._started_daemon = True
        with mock.patch.object(client, "_send_command") as send:
            client.navigate("https://example.com", wait_until="load")
        send.assert_called_once_with(
            "navigate",
            {"url": "https://example.com", "waitUntil": "load"}
        )

    def test_default_wait_until_when_not_cold_start(self):
        client = AgentBrowserClient(session_id="test")
        client._started_daemon = False
        with mock.patch.object(client, "_send_command") as send:
            client.navigate("https://example.com")
        send.assert_called_once_with("navigate", {"url": "https://example.com"})


if __name__ == "__main__":
    unittest.main()
