import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts import source_manager as source_module


class DummyNotebookLMClient:
    def __init__(self):
        self.created_titles = []
        self.added_files = []
        self.next_notebook_id = "nb123"
        self.next_source_ids = ["src123"]

    def create_notebook(self, title: str):
        self.created_titles.append(title)
        return {"id": self.next_notebook_id, "title": title}

    def add_file(self, notebook_id, file_path):
        self.added_files.append((notebook_id, file_path))
        return {
            "source_ids": list(self.next_source_ids),
            "was_chunked": False,
            "chunks": None,
        }


class DummyAuth:
    def __init__(self, authenticated=True):
        self._authenticated = authenticated

    def is_authenticated(self, service: str):
        return self._authenticated

    def restore_auth(self, service: str, client=None):
        return True

    def save_auth(self, service: str, client=None):
        return True


class DummyClient:
    def connect(self):
        return True

    def disconnect(self):
        return True


class DummyDownloader:
    def __init__(self, client, downloads_dir=None):
        self.client = client
        self.downloads_dir = downloads_dir
        self.payload = None

    def download(self, url: str):
        return self.payload


class DummyConverter:
    def __init__(self, output_paths):
        self.output_paths = output_paths

    def convert_epub_to_markdown(self, epub_path, output_path, max_words=350000):
        return self.output_paths


class SourceManagerTests(unittest.TestCase):
    def test_is_zlibrary_url(self):
        manager = source_module.SourceManager(auth_manager=DummyAuth(), client=DummyClient())
        self.assertTrue(manager._is_zlibrary_url("https://zh.zlib.li/book/123"))
        self.assertFalse(manager._is_zlibrary_url("https://example.com/book/123"))

    def test_sanitize_title(self):
        manager = source_module.SourceManager(auth_manager=DummyAuth(), client=DummyClient())
        title = manager._sanitize_title(Path("My_Book [v1] (draft).pdf"))
        self.assertEqual(title, "My Book")

    def test_add_from_url_routes_zlibrary(self):
        manager = source_module.SourceManager(auth_manager=DummyAuth(), client=DummyClient())
        with mock.patch.object(manager, "add_from_zlibrary", return_value={"ok": True}) as add_zlib:
            result = manager.add_from_url("https://zlib.li/book/123")
        self.assertEqual(result, {"ok": True})
        add_zlib.assert_called_once()

        with self.assertRaises(ValueError):
            manager.add_from_url("https://example.com/book/123")

    def test_add_from_zlibrary_requires_auth(self):
        manager = source_module.SourceManager(auth_manager=DummyAuth(authenticated=False), client=DummyClient())
        with self.assertRaises(RuntimeError):
            manager.add_from_zlibrary("https://zlib.li/book/123")

    def test_add_from_zlibrary_converts_epub(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / "book.epub"
            epub_path.write_text("dummy")
            markdown_path = Path(tmpdir) / "book.md"

            downloader = DummyDownloader(client=DummyClient())
            downloader.payload = (epub_path, "epub")
            converter = DummyConverter(output_paths=[markdown_path])

            manager = source_module.SourceManager(
                auth_manager=DummyAuth(),
                client=DummyClient(),
                downloader_cls=lambda client, downloads_dir=None: downloader,
                converter=converter
            )

            with mock.patch.object(manager, "add_from_file", return_value={"ok": True}) as add_from_file:
                result = manager.add_from_zlibrary("https://zlib.li/book/123")

            self.assertEqual(result, {"ok": True})
            add_from_file.assert_called_once_with([markdown_path], None, source_label="zlibrary")

    def test_add_from_file_uploads_and_returns_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "book.pdf"
            file_path.write_text("data")

            notebook_client = DummyNotebookLMClient()
            manager = source_module.SourceManager(
                auth_manager=DummyAuth(),
                client=DummyClient(),
                notebooklm_client=notebook_client,
            )

            with mock.patch.object(source_module, "NotebookLibrary") as library_cls:
                library_cls.return_value.add_notebook.return_value = {"id": "book"}
                result = manager.add_from_file(file_path)

            self.assertTrue(result["success"])
            self.assertEqual(result["notebook_id"], "nb123")
            self.assertEqual(result["source_id"], "src123")
            self.assertEqual(notebook_client.created_titles, ["book"])
            self.assertEqual(notebook_client.added_files[0][0], "nb123")


if __name__ == "__main__":
    unittest.main()
