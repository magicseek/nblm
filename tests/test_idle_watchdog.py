import json
import os
import time
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts import agent_browser_client as abc
from scripts.agent_browser_client import AgentBrowserClient
import scripts.daemon_watchdog as daemon_watchdog


class IdleWatchdogTests(unittest.TestCase):
    def test_record_activity_writes_timestamp_and_owner_pid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_path = Path(tmpdir) / "last_activity.json"
            pid_path = Path(tmpdir) / "watchdog.pid"

            with mock.patch.object(abc, "AGENT_BROWSER_ACTIVITY_FILE", activity_path), \
                mock.patch.object(abc, "AGENT_BROWSER_WATCHDOG_PID_FILE", pid_path), \
                mock.patch.object(AgentBrowserClient, "_ensure_watchdog") as ensure_watchdog:
                os.environ["AGENT_BROWSER_OWNER_PID"] = "12345"

                client = AgentBrowserClient(session_id="test")
                client._record_activity()

                ensure_watchdog.assert_called_once()
                payload = json.loads(activity_path.read_text())
                self.assertIn("timestamp", payload)
                self.assertEqual(payload.get("owner_pid"), 12345)

            os.environ.pop("AGENT_BROWSER_OWNER_PID", None)

    def test_record_activity_preserves_owner_when_env_missing_and_alive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_path = Path(tmpdir) / "last_activity.json"
            pid_path = Path(tmpdir) / "watchdog.pid"

            activity_path.write_text(json.dumps({
                "timestamp": time.time() - 5,
                "owner_pid": 4242
            }))

            with mock.patch.object(abc, "AGENT_BROWSER_ACTIVITY_FILE", activity_path), \
                mock.patch.object(abc, "AGENT_BROWSER_WATCHDOG_PID_FILE", pid_path), \
                mock.patch.object(AgentBrowserClient, "_ensure_watchdog") as ensure_watchdog, \
                mock.patch.object(AgentBrowserClient, "_pid_is_alive", return_value=True):
                os.environ.pop("AGENT_BROWSER_OWNER_PID", None)

                client = AgentBrowserClient(session_id="test")
                client._record_activity()

                ensure_watchdog.assert_called_once()
                payload = json.loads(activity_path.read_text())
                self.assertEqual(payload.get("owner_pid"), 4242)

    def test_record_activity_drops_owner_when_env_missing_and_dead(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_path = Path(tmpdir) / "last_activity.json"
            pid_path = Path(tmpdir) / "watchdog.pid"

            activity_path.write_text(json.dumps({
                "timestamp": time.time() - 5,
                "owner_pid": 4242
            }))

            with mock.patch.object(abc, "AGENT_BROWSER_ACTIVITY_FILE", activity_path), \
                mock.patch.object(abc, "AGENT_BROWSER_WATCHDOG_PID_FILE", pid_path), \
                mock.patch.object(AgentBrowserClient, "_ensure_watchdog") as ensure_watchdog, \
                mock.patch.object(AgentBrowserClient, "_pid_is_alive", return_value=False):
                os.environ.pop("AGENT_BROWSER_OWNER_PID", None)

                client = AgentBrowserClient(session_id="test")
                client._record_activity()

                ensure_watchdog.assert_called_once()
                payload = json.loads(activity_path.read_text())
                self.assertIsNone(payload.get("owner_pid"))

    def test_should_shutdown_on_idle_timeout(self):
        idle_timeout = 600
        self.assertTrue(
            daemon_watchdog.should_shutdown(time.time() - 601, idle_timeout, None)
        )
        self.assertFalse(
            daemon_watchdog.should_shutdown(time.time() - 10, idle_timeout, None)
        )

    def test_should_shutdown_when_owner_missing(self):
        with mock.patch.object(daemon_watchdog, "pid_is_alive", return_value=False):
            self.assertTrue(
                daemon_watchdog.should_shutdown(time.time(), 600, 99999)
            )

    def test_resolve_owner_pid_prefers_file_owner(self):
        self.assertEqual(daemon_watchdog.resolve_owner_pid(111, 222), 222)
        self.assertEqual(daemon_watchdog.resolve_owner_pid(None, 222), 222)
        self.assertEqual(daemon_watchdog.resolve_owner_pid(111, None), 111)


if __name__ == "__main__":
    unittest.main()
