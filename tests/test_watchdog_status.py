import json
import time
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.auth_manager as auth_manager


class WatchdogStatusTests(unittest.TestCase):
    def test_status_reports_activity_and_pids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_path = Path(tmpdir) / "last_activity.json"
            pid_path = Path(tmpdir) / "watchdog.pid"

            activity_payload = {
                "timestamp": time.time() - 120,
                "owner_pid": 555
            }
            activity_path.write_text(json.dumps(activity_payload))
            pid_path.write_text("999")

            with mock.patch.object(auth_manager, "AGENT_BROWSER_ACTIVITY_FILE", activity_path), \
                mock.patch.object(auth_manager, "AGENT_BROWSER_WATCHDOG_PID_FILE", pid_path), \
                mock.patch.object(auth_manager, "_pid_is_alive") as pid_alive, \
                mock.patch.object(auth_manager.AgentBrowserClient, "_daemon_is_running", return_value=True):
                pid_alive.side_effect = lambda pid: pid == 999

                status = auth_manager.get_watchdog_status()

            self.assertEqual(status["watchdog_pid"], 999)
            self.assertTrue(status["watchdog_alive"])
            self.assertEqual(status["owner_pid"], 555)
            self.assertFalse(status["owner_alive"])
            self.assertTrue(110 <= status["idle_seconds"] <= 130)
            self.assertTrue(status["daemon_running"])


if __name__ == "__main__":
    unittest.main()
