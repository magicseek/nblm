import asyncio
import unittest
from unittest import mock
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.ask_question as ask_question


class DummyWrapper:
    """Mock NotebookLMWrapper that returns a successful chat response."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def chat(self, notebook_id: str, message: str) -> dict:
        return {"text": "api answer", "citations": []}


class AskQuestionFallbackTests(unittest.TestCase):
    def test_api_first_success(self):
        """Test that API is tried first and succeeds without browser fallback."""

        async def mock_wrapper_context(*args, **kwargs):
            return DummyWrapper()

        with mock.patch.object(ask_question, "NotebookLMWrapper") as mock_wrapper_cls:
            # Make NotebookLMWrapper return our dummy
            mock_wrapper_cls.return_value = DummyWrapper()

            result = asyncio.run(
                ask_question.ask_notebooklm_api_async(
                    "What is this?",
                    "https://notebooklm.google.com/notebook/abc123"
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertIn("api answer", result["answer"])

    def test_api_extracts_notebook_id_from_url(self):
        """Test that notebook ID is correctly extracted from URL."""
        notebook_id = ask_question._extract_notebook_id_from_url(
            "https://notebooklm.google.com/notebook/abc123"
        )
        self.assertEqual(notebook_id, "abc123")

    def test_api_returns_error_for_invalid_url(self):
        """Test that invalid URL returns error without notebook ID."""
        result = asyncio.run(
            ask_question.ask_notebooklm_api_async(
                "What is this?",
                "https://example.com/invalid"
            )
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "NOTEBOOK_ID_MISSING")


if __name__ == "__main__":
    unittest.main()
