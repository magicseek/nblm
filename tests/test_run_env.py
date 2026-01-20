import os
import sys
import unittest
from pathlib import Path
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.run as run


class RunEnvTests(unittest.TestCase):
    def test_sets_owner_pid_from_detector(self):
        original = os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
        try:
            with mock.patch.object(run, "_detect_owner_pid", return_value=12345):
                run.ensure_owner_pid_env()
            self.assertEqual(os.environ.get("AGENT_BROWSER_OWNER_PID"), "12345")
        finally:
            if original is None:
                os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
            else:
                os.environ["AGENT_BROWSER_OWNER_PID"] = original

    def test_falls_back_to_parent_pid_when_detector_missing(self):
        original = os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
        try:
            with mock.patch.object(run, "_detect_owner_pid", return_value=None), \
                mock.patch.object(run.os, "getppid", return_value=777):
                run.ensure_owner_pid_env()
            self.assertEqual(os.environ.get("AGENT_BROWSER_OWNER_PID"), "777")
        finally:
            if original is None:
                os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
            else:
                os.environ["AGENT_BROWSER_OWNER_PID"] = original

    def test_preserves_owner_pid_when_present(self):
        os.environ["AGENT_BROWSER_OWNER_PID"] = "999"
        run.ensure_owner_pid_env()
        self.assertEqual(os.environ.get("AGENT_BROWSER_OWNER_PID"), "999")

    def test_detect_owner_pid_prefers_agent_process(self):
        process_map = {
            200: (150, "zsh"),
            150: (100, "codex --session"),
            100: (1, "launchd"),
        }

        def fake_get_process_info(pid):
            return process_map.get(pid)

        with mock.patch.object(run.os, "getppid", return_value=200), \
            mock.patch.object(run, "_get_process_info", side_effect=fake_get_process_info):
            self.assertEqual(run._detect_owner_pid(), 150)

    def test_detect_owner_pid_falls_back_to_first_non_shell(self):
        process_map = {
            200: (150, "zsh"),
            150: (100, "iTerm2"),
            100: (1, "launchd"),
        }

        def fake_get_process_info(pid):
            return process_map.get(pid)

        with mock.patch.object(run.os, "getppid", return_value=200), \
            mock.patch.object(run, "_get_process_info", side_effect=fake_get_process_info):
            self.assertEqual(run._detect_owner_pid(), 150)


if __name__ == "__main__":
    unittest.main()
