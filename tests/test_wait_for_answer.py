import unittest
from unittest import mock
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.ask_question import wait_for_answer


class DummyClient:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.index = 0

    def snapshot(self):
        snapshot = self.snapshots[self.index]
        self.index = (self.index + 1) % len(self.snapshots)
        return snapshot


class WaitForAnswerTests(unittest.TestCase):
    def test_returns_answer_when_snapshot_changes(self):
        question = "Test question"
        base = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Answer line one\n"
            "  - paragraph: Answer line two\n"
        )
        snapshots = [
            base + "  - button \"Regenerate 1\" [ref=e2]\n",
            base + "  - button \"Regenerate 2\" [ref=e3]\n",
            base + "  - button \"Regenerate 3\" [ref=e4]\n",
        ]
        client = DummyClient(snapshots)

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=1)

        self.assertIn("Answer line one", answer)
        self.assertIn("Answer line two", answer)


if __name__ == "__main__":
    unittest.main()
