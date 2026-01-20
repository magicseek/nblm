import tempfile
import unittest
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts.zlibrary import epub_converter


class ZlibraryEpubConverterTests(unittest.TestCase):
    def test_count_words_handles_english_and_chinese(self):
        text = "Hello 世界"
        self.assertEqual(epub_converter.count_words(text), 3)

    def test_split_markdown_file_splits_large_chunks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown_path = Path(tmpdir) / "book.md"
            markdown_path.write_text("# Title\n\nalpha beta gamma\n\ndelta epsilon zeta\n")

            chunks = epub_converter.split_markdown_file(markdown_path, max_words=5)

            self.assertEqual(len(chunks), 2)
            self.assertTrue(chunks[0].exists())
            self.assertTrue(chunks[1].exists())
            self.assertIn("alpha beta gamma", chunks[0].read_text())


if __name__ == "__main__":
    unittest.main()
