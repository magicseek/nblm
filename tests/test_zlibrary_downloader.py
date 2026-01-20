import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.zlibrary import downloader as zlib_downloader


class DummyClient:
    def __init__(self, snapshot: str):
        self._snapshot = snapshot
        self.actions = []
        self.download_response = {}

    def navigate(self, url: str, wait_until=None):
        self.actions.append(("navigate", url))

    def snapshot(self, prune: bool = True, interactive: bool = False) -> str:
        return self._snapshot

    def click(self, ref: str):
        self.actions.append(("click", ref))

    def _send_command(self, action: str, params=None):
        self.actions.append(("send", action, params))
        return self.download_response


class ZLibraryDownloaderTests(unittest.TestCase):
    def test_detect_formats_finds_pdf_and_epub(self):
        snapshot = 'link "PDF" [ref=pdf]\nlink "EPUB" [ref=epub]'
        formats = zlib_downloader.ZLibraryDownloader._detect_formats(snapshot)
        self.assertIn("pdf", formats)
        self.assertIn("epub", formats)

    def test_choose_format_prefers_pdf(self):
        self.assertEqual(zlib_downloader.ZLibraryDownloader._choose_format(["epub", "pdf"]), "pdf")
        self.assertEqual(zlib_downloader.ZLibraryDownloader._choose_format(["epub"]), "epub")
        self.assertIsNone(zlib_downloader.ZLibraryDownloader._choose_format([]))

    def test_find_download_ref_matches_format(self):
        snapshot = 'link "Download PDF" [ref=abc]\nlink "Download EPUB" [ref=def]'
        ref = zlib_downloader.ZLibraryDownloader._find_download_ref(snapshot, "pdf")
        self.assertEqual(ref, "abc")

    def test_find_ref_by_keywords_finds_match(self):
        snapshot = 'button "More options" [ref=xyz]'
        ref = zlib_downloader.ZLibraryDownloader._find_ref_by_keywords(snapshot, ["more", "options"])
        self.assertEqual(ref, "xyz")

    def test_download_ref_uses_download_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = DummyClient(snapshot="")
            dl = zlib_downloader.ZLibraryDownloader(client, downloads_dir=Path(tmpdir))
            client.download_response = {
                "suggestedFilename": "book.pdf",
                "path": str(Path(tmpdir) / "zlibrary_123456")
            }

            with mock.patch.object(zlib_downloader.time, "time", return_value=123456):
                temp_path = Path(tmpdir) / "zlibrary_123456"
                temp_path.write_text("data")
                result = dl._download_ref("ref", "pdf")

            self.assertEqual(result, Path(tmpdir) / "book.pdf")
            self.assertTrue(result.exists())
            self.assertIn(("send", "download", {
                "selector": "@ref",
                "path": str(temp_path)
            }), client.actions)

    def test_download_picks_format_and_triggers_download(self):
        snapshot = 'link "Download PDF" [ref=abc]'
        client = DummyClient(snapshot=snapshot)
        with tempfile.TemporaryDirectory() as tmpdir:
            dl = zlib_downloader.ZLibraryDownloader(client, downloads_dir=Path(tmpdir))
            expected_path = Path(tmpdir) / "book.pdf"
            with mock.patch.object(dl, "_download_ref", return_value=expected_path) as download_ref:
                result = dl.download("https://zh.zlib.li/book/1")

            self.assertEqual(result, (expected_path, "pdf"))
            download_ref.assert_called_once_with("abc", "pdf")
            self.assertIn(("navigate", "https://zh.zlib.li/book/1"), client.actions)


if __name__ == "__main__":
    unittest.main()
