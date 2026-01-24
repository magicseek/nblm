#!/usr/bin/env python3
"""
Unified source ingestion for NotebookLM.
"""

import argparse
import json
import os
import re
import sys
import time
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from agent_browser_client import AgentBrowserClient, AgentBrowserError
from auth_manager import AuthManager
from config import DEFAULT_SESSION_ID
from notebook_manager import NotebookLibrary
from notebooklm_kit_client import NotebookLMKitClient, NotebookLMKitError
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

    @staticmethod
    def _find_button_ref(snapshot: str, keywords: List[str]) -> Optional[str]:
        for line in snapshot.splitlines():
            lower = line.lower()
            if "button" not in lower:
                continue
            if not any(keyword in lower for keyword in keywords):
                continue
            match = re.search(r'\[ref=(\w+)\]', line)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _snapshot_has_account_chooser(snapshot: str) -> bool:
        lower = snapshot.lower()
        return "choose an account" in lower or "select an account" in lower

    @staticmethod
    def _find_account_ref(snapshot: str) -> Optional[str]:
        for line in snapshot.splitlines():
            lower = line.lower()
            if "button" not in lower:
                continue
            if "@" not in line and "signed in" not in lower and "signed out" not in lower:
                continue
            match = re.search(r'\[ref=(\w+)\]', line)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _extract_notebook_id_from_url(notebook_url: str) -> Optional[str]:
        if not notebook_url:
            return None
        match = re.search(r"/notebook/([^/?#]+)", notebook_url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _upload_mode() -> str:
        mode = os.environ.get("NOTEBOOKLM_UPLOAD_MODE", "auto").lower()
        if mode in ("auto", "browser", "text"):
            return mode
        return "auto"

    @staticmethod
    def _should_fallback_to_text(upload_error: dict) -> bool:
        code = (upload_error.get("code") or "").upper()
        message = (upload_error.get("error") or "").lower()
        if code in {"DAEMON_UNAVAILABLE", "NOT_CONNECTED"}:
            return True
        return "operation not permitted" in message or "daemon" in message

    @staticmethod
    def _read_text_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="ignore")

    def _extract_text_from_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDF text extraction requires pypdf. "
                "Run: pip install -r requirements.txt"
            ) from exc

        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                parts.append(text)
        return "\n\n".join(parts).strip()

    def _extract_text_for_upload(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".html", ".htm"):
            return self._read_text_file(path)
        if suffix == ".pdf":
            return self._extract_text_from_pdf(path)
        return ""

    def _upload_files_as_text(self, notebook_id: str, paths: List[Path]) -> dict:
        temp_files: List[Path] = []
        source_ids: List[str] = []
        try:
            for path in paths:
                content = self._extract_text_for_upload(path)
                if not content.strip():
                    return {
                        "success": False,
                        "error": f"No extractable text found for {path.name}",
                    }

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
                temp_file.write(content.encode("utf-8", errors="ignore"))
                temp_file.close()
                temp_path = Path(temp_file.name)
                temp_files.append(temp_path)

                result = self.notebooklm_client.add_text(
                    notebook_id,
                    temp_path,
                    title=path.name,
                )
                source_ids.extend(result.get("source_ids", []))

            return {
                "success": True,
                "source_ids": source_ids,
            }
        except RuntimeError as e:
            return {
                "success": False,
                "error": str(e),
                "recovery": "Run: pip install -r requirements.txt",
            }
        except NotebookLMKitError as e:
            return {
                "success": False,
                "error": str(e),
                "recovery": "Run: python scripts/run.py auth_manager.py setup",
            }
        finally:
            for temp_path in temp_files:
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def _list_sources_by_id(self, notebook_id: str) -> dict:
        sources = self.notebooklm_client.list_sources(notebook_id)
        by_id = {}
        for source in sources:
            source_id = source.get("sourceId") or source.get("source_id") or source.get("id")
            if source_id:
                by_id[source_id] = source
        return by_id

    def _wait_for_new_sources(
        self,
        notebook_id: str,
        existing_ids: set,
        expected_titles: List[str],
    ) -> List[str]:
        expected_tokens = [title.lower() for title in expected_titles]
        print("Waiting for NotebookLM to register uploaded source(s)...", file=sys.stderr, flush=True)

        while True:
            sources_by_id = self._list_sources_by_id(notebook_id)
            new_sources = []
            for source_id, source in sources_by_id.items():
                if source_id not in existing_ids:
                    new_sources.append(source)

            if expected_tokens:
                matched = []
                for source in new_sources:
                    title = (source.get("title") or "").lower()
                    if any(token in title for token in expected_tokens):
                        source_id = source.get("sourceId") or source.get("id")
                        if source_id:
                            matched.append(source_id)
                if matched:
                    return matched

            if new_sources:
                return [
                    source.get("sourceId") or source.get("id")
                    for source in new_sources
                    if source.get("sourceId") or source.get("id")
                ]

            time.sleep(2)

    def _upload_files_via_browser(self, notebook_url: str, paths: List[Path]) -> Optional[dict]:
        if not self.auth.is_authenticated("google"):
            return {
                "success": False,
                "error": "Google authentication required",
                "recovery": "Run: python scripts/run.py auth_manager.py setup",
            }

        try:
            if self.client._daemon_is_running():
                self.client.shutdown()
            self.client.connect()
        except AgentBrowserError as e:
            return {
                "success": False,
                "error": e.message,
                "recovery": e.recovery,
                "code": e.code,
            }
        try:
            self.auth.restore_auth("google", client=self.client)
            self.client.navigate(notebook_url)
            time.sleep(2)

            snapshot = self.client.snapshot()
            for _ in range(2):
                if self._snapshot_has_account_chooser(snapshot):
                    account_ref = self._find_account_ref(snapshot)
                    if not account_ref:
                        return {
                            "success": False,
                            "error": "Google account selection required",
                            "recovery": "Run: python scripts/run.py auth_manager.py setup",
                        }
                    self.client.click(account_ref)
                    time.sleep(2)
                    snapshot = self.client.snapshot()
                    continue
                break

            if self.client.check_auth(snapshot):
                return {
                    "success": False,
                    "error": "Google login required",
                    "recovery": "Run: python scripts/run.py auth_manager.py setup",
                }

            add_ref = self._find_button_ref(snapshot, ["add source", "add sources"])
            if add_ref:
                self.client.click(add_ref)
                time.sleep(1)

            try:
                self.client.wait_for_selector("input[type='file']", timeout_ms=10000, state="attached")
            except AgentBrowserError as e:
                return {
                    "success": False,
                    "error": f"Upload input not available: {e.message}",
                    "recovery": "Retry the upload after the page finishes loading",
                }

            self.client.upload("input[type='file']", [str(path) for path in paths])
            return None

        except AgentBrowserError as e:
            return {
                "success": False,
                "error": e.message,
                "recovery": e.recovery,
                "code": e.code,
            }
        finally:
            self.client.disconnect()

    @staticmethod
    def _status_is_ready(status: object) -> bool:
        if isinstance(status, str):
            return status.upper() == "READY"
        return status == 2

    @staticmethod
    def _status_is_failed(status: object) -> bool:
        if isinstance(status, str):
            return status.upper() == "FAILED"
        return status == 3

    def _wait_for_sources_ready(self, notebook_id: str, source_ids: List[str]) -> Optional[dict]:
        if not source_ids:
            return None

        unique_ids = list(dict.fromkeys(source_ids))
        total = len(unique_ids)
        print(f"Waiting for NotebookLM to process {total} source(s)...", file=sys.stderr, flush=True)

        last_ready = None
        while True:
            sources = self.notebooklm_client.list_sources(notebook_id)
            status_by_id = {}
            for source in sources:
                source_id = source.get("sourceId") or source.get("source_id") or source.get("id")
                if source_id:
                    status_by_id[source_id] = source

            ready_count = 0
            failed_ids = []
            for source_id in unique_ids:
                source = status_by_id.get(source_id)
                if not source:
                    continue
                status = source.get("status")
                if self._status_is_failed(status):
                    failed_ids.append(source_id)
                elif self._status_is_ready(status):
                    ready_count += 1

            if failed_ids:
                return {
                    "success": False,
                    "error": "NotebookLM source processing failed",
                    "notebook_id": notebook_id,
                    "source_ids": unique_ids,
                    "failed_source_ids": failed_ids,
                }

            if last_ready is None or ready_count != last_ready:
                print(f"Ready: {ready_count}/{total}", file=sys.stderr, flush=True)
                last_ready = ready_count

            if ready_count >= total:
                return None

            time.sleep(2)

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
        upload_mode = self._upload_mode()

        notebook_url = None
        resolved_notebook_id = notebook_id

        if not notebook_id:
            result = self.notebooklm_client.create_notebook(title)
            notebook_id = result["id"]
            created_notebook = True
            resolved_notebook_id = notebook_id
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

        if not self.auth.is_authenticated("google"):
            return {
                "success": False,
                "error": "Google authentication required",
                "recovery": "Run: python scripts/run.py auth_manager.py setup",
            }

        if upload_mode == "text":
            print("Uploading extracted text instead of raw file...", file=sys.stderr, flush=True)
            text_result = self._upload_files_as_text(resolved_notebook_id, paths)
            if not text_result.get("success"):
                return text_result
            source_ids = text_result.get("source_ids", [])
        else:
            try:
                existing_ids = set(self._list_sources_by_id(resolved_notebook_id).keys())
            except NotebookLMKitError as e:
                return {
                    "success": False,
                    "error": str(e),
                    "recovery": "Run: python scripts/run.py auth_manager.py setup",
                }

            upload_error = self._upload_files_via_browser(notebook_url, paths)
            if upload_error:
                if upload_mode == "auto" and self._should_fallback_to_text(upload_error):
                    print(
                        "Browser upload unavailable; uploading extracted text instead...",
                        file=sys.stderr,
                        flush=True,
                    )
                    text_result = self._upload_files_as_text(resolved_notebook_id, paths)
                    if not text_result.get("success"):
                        return text_result
                    source_ids = text_result.get("source_ids", [])
                else:
                    return upload_error

            if not upload_error:
                expected_titles = [Path(path).name for path in paths]
                try:
                    source_ids = self._wait_for_new_sources(resolved_notebook_id, existing_ids, expected_titles)
                except NotebookLMKitError as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "recovery": "Run: python scripts/run.py auth_manager.py setup",
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

        try:
            wait_error = self._wait_for_sources_ready(resolved_notebook_id, source_ids)
        except NotebookLMKitError as e:
            return {
                "success": False,
                "error": str(e),
                "recovery": "Run: python scripts/run.py auth_manager.py setup",
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
