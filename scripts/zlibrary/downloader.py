#!/usr/bin/env python3
"""
Z-Library download automation using agent-browser.
"""

import re
import time
from pathlib import Path
from typing import Optional

from agent_browser_client import AgentBrowserClient


class ZLibraryDownloader:
    """Download books from Z-Library using agent-browser."""

    def __init__(self, client: AgentBrowserClient, downloads_dir: Optional[Path] = None):
        self.client = client
        self.downloads_dir = downloads_dir or (Path.home() / "Downloads")

    @staticmethod
    def _detect_formats(snapshot: str) -> list[str]:
        formats = set()
        for line in snapshot.splitlines():
            line_lower = line.lower()
            if "pdf" in line_lower:
                formats.add("pdf")
            if "epub" in line_lower:
                formats.add("epub")
        return sorted(formats)

    @staticmethod
    def _choose_format(formats: list[str]) -> Optional[str]:
        if "pdf" in formats:
            return "pdf"
        if "epub" in formats:
            return "epub"
        return None

    @staticmethod
    def _find_download_ref(snapshot: str, file_format: str) -> Optional[str]:
        if not file_format:
            return None
        for line in snapshot.splitlines():
            line_lower = line.lower()
            if file_format in line_lower and ("link" in line_lower or "button" in line_lower):
                match = re.search(r'\[ref=(\w+)\]', line)
                if match:
                    return match.group(1)
        return None

    @staticmethod
    def _find_ref_by_keywords(snapshot: str, keywords: list[str]) -> Optional[str]:
        for line in snapshot.splitlines():
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                if "button" in line_lower or "link" in line_lower:
                    match = re.search(r'\[ref=(\w+)\]', line)
                    if match:
                        return match.group(1)
        return None

    def _download_ref(self, ref: str, file_format: str) -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        temp_name = f"zlibrary_{int(time.time())}"
        temp_path = self.downloads_dir / temp_name

        response = self.client._send_command("download", {
            "selector": f"@{ref}",
            "path": str(temp_path)
        })

        suggested = response.get("suggestedFilename")
        if suggested:
            final_path = self.downloads_dir / suggested
            if temp_path.exists() and final_path != temp_path:
                temp_path.replace(final_path)
            return final_path

        response_path = response.get("path")
        return Path(response_path) if response_path else temp_path

    def download(self, url: str) -> tuple[Path, str]:
        """Download a book from Z-Library URL."""
        self.client.navigate(url)
        time.sleep(2)

        snapshot = self.client.snapshot()
        formats = self._detect_formats(snapshot)
        chosen = self._choose_format(formats)
        ref = self._find_download_ref(snapshot, chosen)

        if not ref:
            more_ref = self._find_ref_by_keywords(snapshot, ["more", "options", "menu", "dots"])
            if more_ref:
                self.client.click(more_ref)
                time.sleep(2)
                snapshot = self.client.snapshot()
                formats = self._detect_formats(snapshot)
                chosen = self._choose_format(formats) or chosen
                ref = self._find_download_ref(snapshot, chosen)

        if not ref:
            ref = self._find_ref_by_keywords(snapshot, ["download"])
            if ref and chosen is None:
                chosen = "unknown"

        if not ref:
            raise RuntimeError("Download link not found")

        file_path = self._download_ref(ref, chosen)
        return file_path, chosen
