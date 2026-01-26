#!/usr/bin/env python3
"""
Unified source ingestion for NotebookLM.
"""

import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from agent_browser_client import AgentBrowserClient
from auth_manager import AuthManager
from config import DEFAULT_SESSION_ID
from notebook_manager import NotebookLibrary
from notebooklm_wrapper import NotebookLMWrapper, NotebookLMError
from zlibrary.downloader import ZLibraryDownloader
from zlibrary import epub_converter


def _prompt_notebook_choice(library: NotebookLibrary, file_title: str) -> Optional[str]:
    """Prompt user to choose between active notebook or create new.

    Returns:
        notebook_id if user chooses existing notebook, None if user wants to create new.
    """
    active = library.get_active_notebook()

    print("\n📁 No notebook specified. Choose an option:")
    print()

    if active:
        active_name = active.get("name", "Unnamed")
        active_id = active.get("id", "")
        print(f"  [1] Upload to active notebook: \"{active_name}\"")
        print(f"  [2] Create new notebook: \"{file_title}\"")
        print()
        sys.stdout.flush()

        while True:
            try:
                choice = input("Enter choice (1 or 2): ").strip()
                if choice == "1":
                    print(f"\n✓ Using active notebook: {active_name}")
                    return active_id
                elif choice == "2":
                    print(f"\n✓ Creating new notebook: {file_title}")
                    return None
                else:
                    print("Please enter 1 or 2")
            except (EOFError, KeyboardInterrupt):
                print("\n\nCancelled.")
                sys.exit(130)
    else:
        # No active notebook - list available notebooks
        notebooks = library.list_notebooks()

        if notebooks:
            print("  [1] Create new notebook")
            print("  [2] Choose from existing notebooks:")
            for i, nb in enumerate(notebooks[:5], start=1):  # Show up to 5
                print(f"      [{i+1}] {nb.get('name', 'Unnamed')}")
            if len(notebooks) > 5:
                print(f"      ... and {len(notebooks) - 5} more")
            print()
            sys.stdout.flush()

            while True:
                try:
                    choice = input("Enter choice (1 for new, or notebook number): ").strip()
                    if choice == "1":
                        print(f"\n✓ Creating new notebook: {file_title}")
                        return None
                    elif choice.isdigit():
                        idx = int(choice) - 2  # Offset for "Create new" option
                        if 0 <= idx < len(notebooks):
                            selected = notebooks[idx]
                            print(f"\n✓ Using notebook: {selected.get('name', 'Unnamed')}")
                            return selected.get("id")
                        else:
                            print(f"Please enter a number between 1 and {len(notebooks) + 1}")
                    else:
                        print("Please enter a valid number")
                except (EOFError, KeyboardInterrupt):
                    print("\n\nCancelled.")
                    sys.exit(130)
        else:
            print(f"  No existing notebooks found.")
            print(f"  Creating new notebook: \"{file_title}\"")
            print()
            return None


class SourceManager:
    """Unified source ingestion for NotebookLM."""

    def __init__(
        self,
        auth_manager: Optional[AuthManager] = None,
        client: Optional[AgentBrowserClient] = None,
        downloader_cls=ZLibraryDownloader,
        converter=epub_converter,
    ):
        self.auth = auth_manager or AuthManager()
        self.client = client or AgentBrowserClient(session_id=DEFAULT_SESSION_ID)
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

    @staticmethod
    def _extract_notebook_id_from_url(notebook_url: str) -> Optional[str]:
        if not notebook_url:
            return None
        match = re.search(r"/notebook/([^/?#]+)", notebook_url)
        if match:
            return match.group(1)
        return None

    async def _wait_for_sources_ready_async(
        self,
        wrapper: NotebookLMWrapper,
        notebook_id: str,
        source_ids: List[str],
    ) -> Optional[dict]:
        """Wait for sources to be ready using async wrapper."""
        if not source_ids:
            return None

        unique_ids = list(dict.fromkeys(source_ids))
        total = len(unique_ids)
        print(f"Waiting for NotebookLM to process {total} source(s)...", file=sys.stderr, flush=True)

        last_ready = None
        while True:
            sources = await wrapper.list_sources(notebook_id)
            status_by_id = {src["source_id"]: src for src in sources}

            ready_count = 0
            for source_id in unique_ids:
                source = status_by_id.get(source_id)
                if not source:
                    continue
                if source.get("is_ready"):
                    ready_count += 1

            if last_ready is None or ready_count != last_ready:
                print(f"Ready: {ready_count}/{total}", file=sys.stderr, flush=True)
                last_ready = ready_count

            if ready_count >= total:
                return None

            await asyncio.sleep(2)

    async def add_from_file(
        self,
        file_path: Union[Path, List[Path]],
        notebook_id: Optional[str] = None,
        source_label: str = "upload",
        interactive: bool = True,
    ) -> dict:
        """Upload local file(s) to NotebookLM."""
        paths = file_path if isinstance(file_path, list) else [file_path]
        for path in paths:
            if not Path(path).exists():
                raise FileNotFoundError(f"File not found: {path}")

        title = self._sanitize_title(Path(paths[0]))
        created_notebook = False

        notebook_url = None
        resolved_notebook_id = notebook_id

        if not self.auth.is_authenticated("google"):
            return {
                "success": False,
                "error": "Google authentication required",
                "recovery": "Run: python scripts/run.py auth_manager.py setup",
            }

        # Prompt user if no notebook specified and interactive mode
        if not notebook_id and interactive:
            library = NotebookLibrary()
            chosen_id = _prompt_notebook_choice(library, title)
            if chosen_id:
                notebook_id = chosen_id
                resolved_notebook_id = notebook_id

        async with NotebookLMWrapper() as wrapper:
            if not notebook_id:
                try:
                    result = await wrapper.create_notebook(title)
                    notebook_id = result["id"]
                    created_notebook = True
                    resolved_notebook_id = notebook_id
                except NotebookLMError as e:
                    return {
                        "success": False,
                        "error": e.message,
                        "recovery": e.recovery,
                    }
            else:
                library = NotebookLibrary()
                notebook = library.get_notebook(notebook_id)
                if notebook:
                    notebook_url = notebook.get("url")
                    resolved_notebook_id = self._extract_notebook_id_from_url(notebook_url) or notebook_id
                else:
                    is_uuid = bool(re.fullmatch(r"[a-f0-9-]{36}", notebook_id or "", re.IGNORECASE))
                    if not is_uuid:
                        return {
                            "success": False,
                            "error": f"Notebook '{notebook_id}' not found in library",
                            "recovery": "Run: python scripts/run.py notebook_manager.py list",
                        }

            if not notebook_url:
                notebook_url = f"https://notebooklm.google.com/notebook/{resolved_notebook_id}"

            # Upload files using the wrapper
            source_ids = []
            try:
                for path in paths:
                    result = await wrapper.add_file(resolved_notebook_id, Path(path))
                    if result.get("source_id"):
                        source_ids.append(result["source_id"])
            except NotebookLMError as e:
                return {
                    "success": False,
                    "error": e.message,
                    "recovery": e.recovery,
                }

            if created_notebook:
                try:
                    library = NotebookLibrary()
                    description = f"Imported from {source_label}: {title}"
                    library.add_notebook(
                        url=notebook_url,
                        name=title,
                        description=description,
                        topics=[source_label],
                    )
                except Exception:
                    pass

            if not source_ids:
                return {"success": False, "error": "Upload failed"}

            # Wait for sources to be ready
            try:
                wait_error = await self._wait_for_sources_ready_async(wrapper, resolved_notebook_id, source_ids)
            except NotebookLMError as e:
                return {
                    "success": False,
                    "error": e.message,
                    "recovery": e.recovery,
                }
            if wait_error:
                return wait_error

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

    async def add_from_zlibrary(self, url: str, notebook_id: Optional[str] = None, interactive: bool = True) -> dict:
        """Download from Z-Library and upload to NotebookLM."""
        if not self.auth.is_authenticated("zlibrary"):
            raise RuntimeError(
                "Z-Library authentication required. "
                "Run: python scripts/run.py auth_manager.py setup --service zlibrary"
            )

        self.client.connect()
        try:
            # Let restore_auth handle navigation - don't navigate here
            self.auth.restore_auth("zlibrary", client=self.client)
            downloader = self.downloader_cls(self.client)
            file_path, file_format = downloader.download(url)
            self.auth.save_auth("zlibrary", client=self.client)
        finally:
            self.client.disconnect()

        if file_format == "epub" or Path(file_path).suffix.lower() == ".epub":
            output_path = Path(tempfile.gettempdir()) / f"{Path(file_path).stem}.md"
            converted = self.converter.convert_epub_to_markdown(file_path, output_path)
            return await self.add_from_file(converted, notebook_id, source_label="zlibrary", interactive=interactive)

        return await self.add_from_file(Path(file_path), notebook_id, source_label="zlibrary", interactive=interactive)

    async def add_from_url(self, url: str, notebook_id: Optional[str] = None, interactive: bool = True) -> dict:
        """Smart routing based on URL pattern."""
        if self._is_zlibrary_url(url):
            return await self.add_from_zlibrary(url, notebook_id, interactive=interactive)
        raise ValueError(f"Unsupported URL: {url}")


async def async_main():
    parser = argparse.ArgumentParser(description="Add sources to NotebookLM")
    parser.add_argument("command", choices=["add"], help="Command to run")
    parser.add_argument("--url", help="Source URL")
    parser.add_argument("--file", help="Local file path")
    parser.add_argument("--notebook-id", help="Existing notebook ID")

    args = parser.parse_args()
    manager = SourceManager()

    if args.command == "add":
        if args.url:
            result = await manager.add_from_url(args.url, args.notebook_id)
        elif args.file:
            result = await manager.add_from_file(Path(args.file), args.notebook_id)
        else:
            raise SystemExit("Provide --url or --file")

        print(json.dumps(result, indent=2))


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
