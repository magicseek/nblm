#!/usr/bin/env python3
"""
Slides Manager for NotebookLM
Generates and manages slide deck artifacts (PDF output).
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from notebooklm_wrapper import NotebookLMWrapper, NotebookLMError
from notebook_manager import NotebookLibrary


def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_notebook_id(notebook_id: Optional[str] = None) -> str:
    """Get notebook ID from argument or active notebook."""
    if notebook_id:
        library = NotebookLibrary()
        notebook = library.get_notebook(notebook_id)
        if notebook:
            url = notebook.get("url", "")
            if "notebook/" in url:
                parts = url.split("notebook/")
                if len(parts) > 1:
                    return parts[1].split("/")[0].split("?")[0]
        return notebook_id

    library = NotebookLibrary()
    active = library.get_active_notebook()
    if not active:
        raise ValueError("No active notebook. Run: python scripts/run.py notebook_manager.py activate --id <id>")

    url = active.get("url", "")
    if "notebook/" in url:
        parts = url.split("notebook/")
        if len(parts) > 1:
            return parts[1].split("/")[0].split("?")[0]
    raise ValueError(f"Cannot extract notebook ID from URL: {url}")


async def cmd_generate(args):
    """Generate a slide deck from notebook content."""
    notebook_id = get_notebook_id(args.notebook_id)

    async with NotebookLMWrapper() as wrapper:
        print("Generating slide deck...")
        print(f"   Format: {args.format}")
        print(f"   Length: {args.length}")
        if args.instructions:
            print(f"   Instructions: {args.instructions[:50]}...")

        result = await wrapper.generate_slide_deck(
            notebook_id,
            instructions=args.instructions or "",
            slide_format=args.format,
            slide_length=args.length,
        )

        task_id = result.get("task_id")
        print(f"   Task ID: {task_id}")

        if args.wait:
            print("\nWaiting for generation to complete...")
            final = await wrapper.wait_for_audio(
                notebook_id,
                task_id,
                timeout=args.timeout,
                poll_interval=10,
            )

            if final.get("is_complete"):
                print("Slide deck generation complete!")
                if args.output:
                    print(f"Downloading to: {args.output}")
                    path = await wrapper.download_slide_deck(notebook_id, args.output, task_id)
                    print(f"Saved to: {path}")
                elif final.get("url"):
                    print(f"URL: {final['url']}")
            elif final.get("is_failed"):
                print(f"Generation failed: {final.get('error', 'Unknown error')}")
                sys.exit(1)
        else:
            print("\nUse --wait to wait for completion, or check status with:")
            print(f"   python scripts/run.py slides_manager.py status --task-id {task_id}")
            print(json.dumps(result, indent=2))


async def cmd_download(args):
    """Download a slide deck to a local file."""
    notebook_id = get_notebook_id(args.notebook_id)

    async with NotebookLMWrapper() as wrapper:
        print(f"Downloading slide deck to: {args.output}")
        path = await wrapper.download_slide_deck(
            notebook_id,
            args.output,
            artifact_id=args.artifact_id,
        )
        print(f"Saved to: {path}")


async def cmd_list(args):
    """List slide deck artifacts in a notebook."""
    notebook_id = get_notebook_id(args.notebook_id)

    async with NotebookLMWrapper() as wrapper:
        artifact_type = args.type or "slide-deck"
        artifacts = await wrapper.list_artifacts(notebook_id, artifact_type=artifact_type)

        if not artifacts:
            print("No slide decks found.")
            return

        print(f"\nSlide decks ({len(artifacts)} total):\n")
        for artifact in artifacts:
            status_icon = "done" if artifact.get("status") == "completed" else "pending"
            print(f"  [{status_icon}] {artifact.get('title', 'Untitled')}")
            print(f"     ID: {artifact['artifact_id']}")
            if artifact.get("created_at"):
                print(f"     Created: {artifact['created_at']}")
            if artifact.get("url"):
                print(f"     URL: {artifact['url']}")
            print()


async def cmd_status(args):
    """Check status of a slide deck generation task."""
    notebook_id = get_notebook_id(args.notebook_id)

    async with NotebookLMWrapper() as wrapper:
        status = await wrapper.get_audio_status(notebook_id, args.task_id)

        if status.get("is_complete"):
            print("Generation complete!")
            if status.get("url"):
                print(f"URL: {status['url']}")
        elif status.get("is_failed"):
            print(f"Generation failed: {status.get('error', 'Unknown error')}")
        else:
            progress = status.get("progress")
            if progress:
                print(f"In progress: {progress}%")
            else:
                print(f"Status: {status.get('status', 'processing')}")

        if args.json:
            print(json.dumps(status, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Generate and manage NotebookLM slide decks (PDF output)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    p = subparsers.add_parser("generate", help="Generate a slide deck")
    p.add_argument("--notebook-id", help="Notebook ID (uses active if not specified)")
    p.add_argument("--instructions", help="Custom instructions for the slide deck")
    p.add_argument(
        "--format",
        choices=["DETAILED_DECK", "PRESENTER_SLIDES"],
        default="DETAILED_DECK",
        help="Slide format (default: DETAILED_DECK)",
    )
    p.add_argument(
        "--length",
        choices=["SHORT", "DEFAULT"],
        default="DEFAULT",
        help="Slide deck length (default: DEFAULT)",
    )
    p.add_argument("--wait", action="store_true", help="Wait for generation to complete")
    p.add_argument("--output", "-o", help="Download path as PDF (requires --wait)")
    p.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")

    # Download command
    p = subparsers.add_parser("download", help="Download a slide deck as PDF")
    p.add_argument("output", help="Output file path (.pdf)")
    p.add_argument("--artifact-id", help="Artifact ID (uses latest if not specified)")
    p.add_argument("--notebook-id", help="Notebook ID (uses active if not specified)")

    # List command
    p = subparsers.add_parser("list", help="List slide deck artifacts")
    p.add_argument("--notebook-id", help="Notebook ID (uses active if not specified)")
    p.add_argument(
        "--type",
        choices=["slide-deck"],
        default="slide-deck",
        help="Artifact type filter (default: slide-deck)",
    )

    # Status command
    p = subparsers.add_parser("status", help="Check slide deck generation status")
    p.add_argument("--task-id", required=True, help="Task ID from generate command")
    p.add_argument("--notebook-id", help="Notebook ID (uses active if not specified)")
    p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  # Generate a slide deck and wait for completion")
        print("  python scripts/run.py slides_manager.py generate --wait --output presentation.pdf")
        print()
        print("  # Generate with custom format and instructions")
        print('  python scripts/run.py slides_manager.py generate --format PRESENTER_SLIDES --instructions "Focus on key findings"')
        print()
        print("  # Check generation status")
        print("  python scripts/run.py slides_manager.py status --task-id <task-id>")
        print()
        print("  # Download latest slide deck")
        print("  python scripts/run.py slides_manager.py download ./presentation.pdf")
        print()
        print("  # List all slide decks")
        print("  python scripts/run.py slides_manager.py list")
        return 1

    cmd_map = {
        "generate": cmd_generate,
        "download": cmd_download,
        "list": cmd_list,
        "status": cmd_status,
    }

    try:
        asyncio.run(cmd_map[args.command](args))
        return 0
    except NotebookLMError as e:
        print(f"[{e.code}]: {e.message}")
        if e.recovery:
            print(f"Recovery: {e.recovery}")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
