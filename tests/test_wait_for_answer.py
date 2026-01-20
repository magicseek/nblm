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

    def test_returns_answer_even_if_thinking_present(self):
        question = "Test question"
        snapshot = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Answer line one\n"
            "  - text: Thinking...\n"
        )
        client = DummyClient([snapshot])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.1)

        self.assertIn("Answer line one", answer)

    def test_waits_for_final_answer_after_gist_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Getting the gist...\n"
            "  - text: Gathering the facts...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotIn("Getting the gist", answer)
        self.assertNotIn("Gathering the facts", answer)

    def test_waits_for_final_answer_after_consulting_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Consulting your sources...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotIn("Consulting your sources", answer)

    def test_waits_for_final_answer_after_scanning_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Scanning the text...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotIn("Scanning the text", answer)

    def test_waits_for_final_answer_after_reading_inputs_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Reading your inputs...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotIn("Reading your inputs", answer)

    def test_waits_for_final_answer_after_sifting_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Sifting through pages...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotIn("Sifting through pages", answer)

    def test_waits_for_answer_when_only_question_repeated(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - heading \"Test question\" [ref=e2]\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotEqual(answer.strip(), question)

    def test_waits_for_answer_when_question_echoed_with_placeholder(self):
        question = "Test question"
        placeholder = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - text: Test question\n"
            "  - text: Sifting through pages...\n"
        )
        final = (
            "  - heading \"Test question\" [ref=e1]\n"
            "  - paragraph: Final answer line\n"
        )
        client = DummyClient([placeholder, placeholder, placeholder, final, final, final])

        with mock.patch("scripts.ask_question.time.sleep", return_value=None):
            answer = wait_for_answer(client, question, timeout=0.5)

        self.assertIn("Final answer line", answer)
        self.assertNotEqual(answer.strip(), question)


if __name__ == "__main__":
    unittest.main()
