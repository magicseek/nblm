#!/usr/bin/env python3
"""
NotebookLM Question Interface
Uses agent-browser for token-efficient browser automation
"""

import argparse
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from notebook_manager import NotebookLibrary
from agent_browser_client import AgentBrowserClient, AgentBrowserError


# Follow-up reminder for comprehensive research
FOLLOW_UP_REMINDER = (
    "\n\n---\n"
    "**Is that ALL you need to know?** "
    "You can ask another question! Review the user's original request. "
    "If anything is unclear or missing, ask a comprehensive follow-up question "
    "(each question opens a fresh context)."
)


def find_input_ref(client: AgentBrowserClient, snapshot: str) -> str:
    """Find the query input element ref"""
    # Try common patterns for NotebookLM input
    input_ref = client.find_ref_by_role(snapshot, "textbox", "ask")
    if input_ref:
        return input_ref

    input_ref = client.find_ref_by_role(snapshot, "textbox", "query")
    if input_ref:
        return input_ref

    input_ref = client.find_ref_by_role(snapshot, "textbox", "source")
    if input_ref:
        return input_ref

    # Fallback: find any textbox
    input_ref = client.find_ref_by_role(snapshot, "textbox")
    if input_ref:
        return input_ref

    return None


def wait_for_answer(client: AgentBrowserClient, timeout: int = 120) -> str:
    """Wait for NotebookLM answer to stabilize"""
    deadline = time.time() + timeout
    last_snapshot = None
    stable_count = 0

    while time.time() < deadline:
        snapshot = client.snapshot()

        # Check if still thinking
        if "thinking" in snapshot.lower() or "loading" in snapshot.lower():
            time.sleep(1)
            continue

        # Check for stability
        if snapshot == last_snapshot:
            stable_count += 1
            if stable_count >= 3:
                return extract_answer(snapshot)
        else:
            stable_count = 0
            last_snapshot = snapshot

        time.sleep(1)

    raise AgentBrowserError(
        code="TIMEOUT",
        message=f"No response within {timeout} seconds",
        recovery="Try again or check if notebook is accessible"
    )


def extract_answer(snapshot: str) -> str:
    """Extract the latest answer from accessibility snapshot"""
    # Look for response content in snapshot
    # NotebookLM typically has responses in specific regions
    lines = snapshot.split('\n')

    # Find the last substantial text block (likely the answer)
    answer_lines = []
    in_response = False

    for line in lines:
        # Look for response indicators
        if 'response' in line.lower() or 'answer' in line.lower() or 'message' in line.lower():
            in_response = True

        if in_response and line.strip():
            # Extract text content (remove ref markers)
            clean_line = re.sub(r'\[ref=\w+\]', '', line).strip()
            if clean_line and len(clean_line) > 10:
                answer_lines.append(clean_line)

    if answer_lines:
        return '\n'.join(answer_lines)

    # Fallback: return relevant portion of snapshot
    return snapshot


def ask_notebooklm(question: str, notebook_url: str, show_browser: bool = False) -> dict:
    """
    Ask a question to NotebookLM

    Returns:
        dict with status, answer, and optional error
    """
    auth = AuthManager()

    if not auth.is_authenticated():
        return {
            "status": "error",
            "error": {
                "code": "AUTH_REQUIRED",
                "message": "Not authenticated with Google",
                "recovery": "Run: python scripts/run.py auth_manager.py setup"
            }
        }

    print(f"💬 Asking: {question[:80]}{'...' if len(question) > 80 else ''}")
    print(f"📚 Notebook: {notebook_url[:60]}...")

    client = AgentBrowserClient(session_id="notebooklm", headed=show_browser)

    try:
        client.connect()

        # Navigate to notebook
        client.navigate(notebook_url)
        time.sleep(2)  # Allow page to load

        # Get initial snapshot
        snapshot = client.snapshot()

        # Check if auth is needed
        if client.check_auth(snapshot):
            return {
                "status": "error",
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Google login required",
                    "recovery": "Run: python scripts/run.py auth_manager.py setup"
                },
                "snapshot": snapshot[:500]
            }

        # Find input element
        print("⏳ Finding query input...")
        input_ref = find_input_ref(client, snapshot)

        if not input_ref:
            return {
                "status": "error",
                "error": {
                    "code": "ELEMENT_NOT_FOUND",
                    "message": "Cannot find query input on page",
                    "recovery": "Check notebook URL or view snapshot for diagnosis"
                },
                "snapshot": snapshot[:500]
            }

        # Type question and submit
        print("⌨️ Typing question...")
        client.fill(ref=input_ref, text=question)
        client.press_key("Enter")

        # Wait for answer
        print("⏳ Waiting for answer...")
        time.sleep(2)  # Initial wait

        answer = wait_for_answer(client, timeout=120)

        print("✅ Got answer!")

        return {
            "status": "success",
            "question": question,
            "answer": answer + FOLLOW_UP_REMINDER,
            "notebook_url": notebook_url
        }

    except AgentBrowserError as e:
        return {
            "status": "error",
            "error": e.to_dict()
        }
    finally:
        client.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Ask NotebookLM a question')

    parser.add_argument('--question', required=True, help='Question to ask')
    parser.add_argument('--notebook-url', help='NotebookLM notebook URL')
    parser.add_argument('--notebook-id', help='Notebook ID from library')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')

    args = parser.parse_args()

    # Resolve notebook URL
    notebook_url = args.notebook_url

    if not notebook_url and args.notebook_id:
        library = NotebookLibrary()
        notebook = library.get_notebook(args.notebook_id)
        if notebook:
            notebook_url = notebook['url']
        else:
            print(f"❌ Notebook '{args.notebook_id}' not found")
            return 1

    if not notebook_url:
        library = NotebookLibrary()
        active = library.get_active_notebook()
        if active:
            notebook_url = active['url']
            print(f"📚 Using active notebook: {active['name']}")
        else:
            notebooks = library.list_notebooks()
            if notebooks:
                print("\n📚 Available notebooks:")
                for nb in notebooks:
                    mark = " [ACTIVE]" if nb.get('id') == library.active_notebook_id else ""
                    print(f"  {nb['id']}: {nb['name']}{mark}")
                print("\nSpecify with --notebook-id or set active:")
                print("python scripts/run.py notebook_manager.py activate --id ID")
            else:
                print("❌ No notebooks in library. Add one first:")
                print("python scripts/run.py notebook_manager.py add --url URL --name NAME --description DESC --topics TOPICS")
            return 1

    # Ask the question
    result = ask_notebooklm(
        question=args.question,
        notebook_url=notebook_url,
        show_browser=args.show_browser
    )

    if result["status"] == "success":
        print()
        print("=" * 60)
        print(f"Question: {args.question}")
        print("=" * 60)
        print()
        print(result["answer"])
        print()
        print("=" * 60)
        return 0
    else:
        error = result["error"]
        print()
        print(f"❌ [{error['code']}]: {error['message']}")
        print(f"🔧 Recovery: {error['recovery']}")
        if result.get("snapshot"):
            print(f"📄 Page state:\n{result['snapshot']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
