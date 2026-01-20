#!/usr/bin/env python3
"""
Unified source ingestion for NotebookLM.
"""

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from agent_browser_client import AgentBrowserClient
from auth_manager import AuthManager
from config import DEFAULT_SESSION_ID
from notebook_manager import NotebookLibrary
from notebooklm_kit_client import NotebookLMKitClient
from zlibrary.downloader import ZLibraryDownloader
from zlibrary import epub_converter


class SourceManager:
    """Unified source ingestion for NotebookLM."""

    def __init__(
        self,
        auth_manager: Optional[AuthManager] = None,
        client: Optional[AgentBrowserClient] = None,
        notebooklm_client: Optional[NotebookLMKitClient] = None,
        downloader_cls=ZLibraryDownloader,
        converter=epub_converter,
    ):
        self.auth = auth_manager or AuthManager()
        self.client = client or AgentBrowserClient(session_id=DEFAULT_SESSION_ID)
        self.notebooklm_client = notebooklm_client or NotebookLMKitClient(auth_provider=self.auth)
        self.downloader_cls = downloader_cls
        self.converter = converter

    @staticmethod
    def _is_zlibrary_url(url: str) -> bool:
        domains = ["zlib.li", "z-lib.org", "zlibrary.org", "zh.zlib.li"]
        return any(domain in url for domain in domains)

    @staticmethod
    def _sanitize_title(file_path: Path) -> str:
        title = file_path.stem
        title = re.sub(r'_part\d+$', '', title)
        title = title.replace('_', ' ')
        title = re.sub(r'\[.*?\]', '', title)
        title = re.sub(r'\(.*?\)', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 50:
            title = title[:50] + "..."
        return title

    def add_from_file(
        self,
        file_path: Union[Path, List[Path]],
        notebook_id: Optional[str] = None,
        source_label: str = "upload",
    ) -> dict:
        """Upload local file(s) to NotebookLM."""
        paths = file_path if isinstance(file_path, list) else [file_path]
        for path in paths:
            if not Path(path).exists():
                raise FileNotFoundError(f"File not found: {path}")

        title = self._sanitize_title(Path(paths[0]))
        created_notebook = False

        if not notebook_id:
            result = self.notebooklm_client.create_notebook(title)
            notebook_id = result["id"]
            created_notebook = True

        source_ids = []
        for path in paths:
            result = self.notebooklm_client.add_file(notebook_id, Path(path))
            source_ids.extend(result.get("source_ids", []))

        if created_notebook:
            try:
                library = NotebookLibrary()
                url = f"https://notebooklm.google.com/notebook/{notebook_id}"
                description = f"Imported from {source_label}: {title}"
                library.add_notebook(
                    url=url,
                    name=title,
                    description=description,
                    topics=[source_label],
                )
            except Exception:
                pass

        if not source_ids:
            return {"success": False, "error": "Upload failed"}

        if len(paths) > 1:
            return {
                "success": True,
                "notebook_id": notebook_id,
                "source_ids": source_ids,
                "title": title,
                "chunks": len(paths)
            }

        return {
            "success": True,
            "notebook_id": notebook_id,
            "source_id": source_ids[0],
            "title": title
        }

    def add_from_zlibrary(self, url: str, notebook_id: Optional[str] = None) -> dict:
        """Download from Z-Library and upload to NotebookLM."""
        if not self.auth.is_authenticated("zlibrary"):
            raise RuntimeError(
                "Z-Library authentication required. "
                "Run: python scripts/run.py auth_manager.py setup --service zlibrary"
            )

        self.client.connect()
        try:
            self.auth.restore_auth("zlibrary", client=self.client)
            downloader = self.downloader_cls(self.client)
            file_path, file_format = downloader.download(url)
            self.auth.save_auth("zlibrary", client=self.client)
        finally:
            self.client.disconnect()

        if file_format == "epub" or Path(file_path).suffix.lower() == ".epub":
            output_path = Path(tempfile.gettempdir()) / f"{Path(file_path).stem}.md"
            converted = self.converter.convert_epub_to_markdown(file_path, output_path)
            return self.add_from_file(converted, notebook_id, source_label="zlibrary")

        return self.add_from_file(Path(file_path), notebook_id, source_label="zlibrary")

    def add_from_url(self, url: str, notebook_id: Optional[str] = None) -> dict:
        """Smart routing based on URL pattern."""
        if self._is_zlibrary_url(url):
            return self.add_from_zlibrary(url, notebook_id)
        raise ValueError(f"Unsupported URL: {url}")


def main():
    parser = argparse.ArgumentParser(description="Add sources to NotebookLM")
    parser.add_argument("command", choices=["add"], help="Command to run")
    parser.add_argument("--url", help="Source URL")
    parser.add_argument("--file", help="Local file path")
    parser.add_argument("--notebook-id", help="Existing notebook ID")

    args = parser.parse_args()
    manager = SourceManager()

    if args.command == "add":
        if args.url:
            result = manager.add_from_url(args.url, args.notebook_id)
        elif args.file:
            result = manager.add_from_file(Path(args.file), args.notebook_id)
        else:
            raise SystemExit("Provide --url or --file")

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
