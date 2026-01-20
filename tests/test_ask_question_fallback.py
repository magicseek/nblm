import unittest
from unittest import mock
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.ask_question as ask_question


class DummyBrowser:
    def connect(self):
        raise ask_question.AgentBrowserError(
            code="DAEMON_UNAVAILABLE",
            message="Daemon failed to start within timeout",
            recovery="Check Node.js installation"
        )

    def disconnect(self):
        return None


class DummyKitClient:
    def chat(self, notebook_id: str, prompt: str) -> dict:
        return {"text": "api answer"}


class AskQuestionFallbackTests(unittest.TestCase):
    def test_fallback_to_api_when_daemon_unavailable(self):
        with mock.patch.object(ask_question, "AgentBrowserClient", return_value=DummyBrowser()), \
            mock.patch.object(ask_question.AuthManager, "is_authenticated", return_value=False), \
            mock.patch.object(ask_question, "NotebookLMKitClient", return_value=DummyKitClient()), \
            mock.patch.dict(
                ask_question.os.environ,
                {"NOTEBOOKLM_AUTH_TOKEN": "env-token", "NOTEBOOKLM_COOKIES": "SID=env"},
                clear=False,
            ):
            result = ask_question.ask_notebooklm(
                "What is this?",
                "https://notebooklm.google.com/notebook/abc123"
            )

        self.assertEqual(result["status"], "success")
        self.assertIn("api answer", result["answer"])


if __name__ == "__main__":
    unittest.main()
