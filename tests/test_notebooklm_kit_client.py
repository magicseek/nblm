import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.notebooklm_kit_client import NotebookLMKitClient


class DummyAuthProvider:
    def __init__(self):
        self.calls = []

    def get_notebooklm_credentials(self, client=None, force_refresh: bool = False):
        self.calls.append(force_refresh)
        return {"auth_token": f"token-{len(self.calls)}", "cookies": "SID=abc"}


class NotebookLMKitClientTests(unittest.TestCase):
    def test_create_notebook_uses_bridge_and_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge_path = Path(tmpdir) / "bridge.mjs"
            bridge_path.write_text("// placeholder")
            runner = mock.Mock()
            runner.return_value = mock.Mock(
                returncode=0,
                stdout=json.dumps({"notebookId": "nb123", "title": "My Notebook"}),
                stderr="",
            )
            client = NotebookLMKitClient(
                auth_provider=DummyAuthProvider(),
                runner=runner,
                node_path="node",
                script_path=bridge_path,
            )

            result = client.create_notebook("My Notebook")

            self.assertEqual(result["id"], "nb123")
            self.assertEqual(result["title"], "My Notebook")
            cmd = runner.call_args[0][0]
            self.assertEqual(cmd[0], "node")
            self.assertEqual(cmd[1], str(bridge_path))
            self.assertIn("create-notebook", cmd)
            env = runner.call_args[1]["env"]
            self.assertEqual(env["NOTEBOOKLM_AUTH_TOKEN"], "token-1")
            self.assertEqual(env["NOTEBOOKLM_COOKIES"], "SID=abc")

    def test_add_file_returns_source_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge_path = Path(tmpdir) / "bridge.mjs"
            bridge_path.write_text("// placeholder")
            runner = mock.Mock()
            runner.return_value = mock.Mock(
                returncode=0,
                stdout=json.dumps({"sourceIds": ["src1", "src2"], "wasChunked": True}),
                stderr="",
            )
            client = NotebookLMKitClient(
                auth_provider=DummyAuthProvider(),
                runner=runner,
                node_path="node",
                script_path=bridge_path,
            )

            result = client.add_file("nb123", Path("/tmp/file.pdf"))

            self.assertEqual(result["source_ids"], ["src1", "src2"])
            self.assertTrue(result["was_chunked"])

    def test_create_notebook_retries_on_auth_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge_path = Path(tmpdir) / "bridge.mjs"
            bridge_path.write_text("// placeholder")

            responses = [
                mock.Mock(returncode=1, stdout="", stderr="401 Unauthorized"),
                mock.Mock(returncode=0, stdout=json.dumps({"notebookId": "nb1"}), stderr=""),
            ]
            runner = mock.Mock(side_effect=responses)
            auth = DummyAuthProvider()
            client = NotebookLMKitClient(
                auth_provider=auth,
                runner=runner,
                node_path="node",
                script_path=bridge_path,
            )

            result = client.create_notebook("Title")

            self.assertEqual(result["id"], "nb1")
            self.assertEqual(auth.calls, [False, True])
            self.assertEqual(runner.call_count, 2)

    def test_chat_returns_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge_path = Path(tmpdir) / "bridge.mjs"
            bridge_path.write_text("// placeholder")
            runner = mock.Mock()
            runner.return_value = mock.Mock(
                returncode=0,
                stdout=json.dumps({"text": "api answer", "citations": [1]}),
                stderr="",
            )
            client = NotebookLMKitClient(
                auth_provider=DummyAuthProvider(),
                runner=runner,
                node_path="node",
                script_path=bridge_path,
            )

            result = client.chat("nb123", "What is this?")

            self.assertEqual(result["text"], "api answer")
            cmd = runner.call_args[0][0]
            self.assertIn("chat", cmd)


if __name__ == "__main__":
    unittest.main()
