import asyncio
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
        """Test that add_from_url routes Z-Library URLs correctly (async)."""
        manager = source_module.SourceManager(auth_manager=DummyAuth(), client=DummyClient())

        async def mock_add_from_zlibrary(url, notebook_id=None):
            return {"ok": True}

        with mock.patch.object(manager, "add_from_zlibrary", side_effect=mock_add_from_zlibrary) as add_zlib:
            result = asyncio.run(manager.add_from_url("https://zlib.li/book/123"))
        self.assertEqual(result, {"ok": True})
        add_zlib.assert_called_once()

        with self.assertRaises(ValueError):
            asyncio.run(manager.add_from_url("https://example.com/book/123"))

    def test_add_from_zlibrary_requires_auth(self):
        """Test that add_from_zlibrary raises RuntimeError when not authenticated (async)."""
        manager = source_module.SourceManager(auth_manager=DummyAuth(authenticated=False), client=DummyClient())
        with self.assertRaises(RuntimeError):
            asyncio.run(manager.add_from_zlibrary("https://zlib.li/book/123"))

    def test_add_from_zlibrary_converts_epub(self):
        """Test that add_from_zlibrary converts EPUB files (async)."""
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

            async def mock_add_from_file(file_path, notebook_id=None, source_label="upload"):
                return {"ok": True}

            with mock.patch.object(manager, "add_from_file", side_effect=mock_add_from_file) as add_from_file:
                result = asyncio.run(manager.add_from_zlibrary("https://zlib.li/book/123"))

            self.assertEqual(result, {"ok": True})
            add_from_file.assert_called_once()


if __name__ == "__main__":
    unittest.main()
