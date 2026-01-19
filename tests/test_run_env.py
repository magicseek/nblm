import os
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.run as run


class RunEnvTests(unittest.TestCase):
    def test_sets_owner_pid_when_missing(self):
        original = os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
        try:
            run.ensure_owner_pid_env()
            self.assertEqual(os.environ.get("AGENT_BROWSER_OWNER_PID"), str(os.getppid()))
        finally:
            if original is None:
                os.environ.pop("AGENT_BROWSER_OWNER_PID", None)
            else:
                os.environ["AGENT_BROWSER_OWNER_PID"] = original

    def test_preserves_owner_pid_when_present(self):
        os.environ["AGENT_BROWSER_OWNER_PID"] = "999"
        run.ensure_owner_pid_env()
        self.assertEqual(os.environ.get("AGENT_BROWSER_OWNER_PID"), "999")


if __name__ == "__main__":
    unittest.main()
