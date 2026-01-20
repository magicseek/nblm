#!/usr/bin/env python3
"""
Universal runner for NotebookLM skill scripts
Ensures all scripts run with the correct virtual environment
"""

import os
import sys
import subprocess
from pathlib import Path


AGENT_PROCESS_HINTS = ("codex", "claude", "claude-code", "claude_code")
IGNORED_PROCESS_NAMES = {
    "bash",
    "dash",
    "fish",
    "sh",
    "zsh",
    "python",
    "python3",
    "node",
    "npm",
}


def _get_process_info(pid: int):
    """Return (ppid, command) for a PID, or None on failure."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    line = result.stdout.strip()
    if not line:
        return None

    parts = line.split(None, 2)
    if len(parts) < 2:
        return None

    try:
        ppid = int(parts[1])
    except ValueError:
        return None

    command = parts[2] if len(parts) > 2 else ""
    return ppid, command


def _looks_like_agent(command: str) -> bool:
    lower = command.lower()
    return any(hint in lower for hint in AGENT_PROCESS_HINTS)


def _is_ignored_command(command: str) -> bool:
    if not command:
        return True
    base = Path(command.split()[0]).name.lower()
    return base in IGNORED_PROCESS_NAMES


def _detect_owner_pid():
    """Best-effort owner PID detection for CLI agents."""
    if os.name == "nt":
        return os.getppid()

    pid = os.getppid()
    fallback_pid = None
    seen = set()

    for _ in range(20):
        if pid <= 1 or pid in seen:
            break
        seen.add(pid)

        info = _get_process_info(pid)
        if not info:
            break

        ppid, command = info
        if _looks_like_agent(command):
            return pid
        if fallback_pid is None and not _is_ignored_command(command):
            fallback_pid = pid

        if not ppid or ppid == pid:
            break
        pid = ppid

    return fallback_pid


def get_venv_python():
    """Get the virtual environment Python executable"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"

    if os.name == 'nt':  # Windows
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:  # Unix/Linux/Mac
        venv_python = venv_dir / "bin" / "python"

    return venv_python


def ensure_venv():
    """Ensure virtual environment exists"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"
    setup_script = skill_dir / "scripts" / "setup_environment.py"

    # Check if venv exists
    if not venv_dir.exists():
        print("🔧 First-time setup: Creating virtual environment...")
        print("   This may take a minute...")

        # Run setup with system Python
        result = subprocess.run([sys.executable, str(setup_script)])
        if result.returncode != 0:
            print("❌ Failed to set up environment")
            sys.exit(1)

        print("✅ Environment ready!")

    return get_venv_python()


def ensure_node_deps():
    """Ensure Node.js dependencies are installed"""
    skill_dir = Path(__file__).parent.parent
    package_json = skill_dir / "package.json"
    node_modules = skill_dir / "node_modules"

    if not package_json.exists():
        return  # No Node.js dependencies needed

    if not node_modules.exists():
        print("📦 Installing agent-browser...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(skill_dir),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"⚠️ npm install failed: {result.stderr}")
            print("   Please ensure Node.js and npm are installed")
        else:
            print("✅ agent-browser installed")


def ensure_owner_pid_env():
    """Ensure agent-browser owner PID is set for watchdog cleanup"""
    if not os.environ.get("AGENT_BROWSER_OWNER_PID"):
        owner_pid = _detect_owner_pid()
        if owner_pid is None:
            owner_pid = os.getppid()
        os.environ["AGENT_BROWSER_OWNER_PID"] = str(owner_pid)


def main():
    """Main runner"""
    if len(sys.argv) < 2:
        print("Usage: python run.py <script_name> [args...]")
        print("\nAvailable scripts:")
        print("  ask_question.py    - Query NotebookLM")
        print("  notebook_manager.py - Manage notebook library")
        print("  session_manager.py  - Manage sessions")
        print("  auth_manager.py     - Handle authentication")
        print("  cleanup_manager.py  - Clean up skill data")
        sys.exit(1)

    script_name = sys.argv[1]
    script_args = sys.argv[2:]

    # Handle both "scripts/script.py" and "script.py" formats
    if script_name.startswith('scripts/'):
        # Remove the scripts/ prefix if provided
        script_name = script_name[8:]  # len('scripts/') = 8

    # Ensure .py extension
    if not script_name.endswith('.py'):
        script_name += '.py'

    # Get script path
    skill_dir = Path(__file__).parent.parent
    script_path = skill_dir / "scripts" / script_name

    if not script_path.exists():
        print(f"❌ Script not found: {script_name}")
        print(f"   Working directory: {Path.cwd()}")
        print(f"   Skill directory: {skill_dir}")
        print(f"   Looked for: {script_path}")
        sys.exit(1)

    # Ensure venv exists and get Python executable
    venv_python = ensure_venv()
    ensure_node_deps()
    ensure_owner_pid_env()

    # Build command
    cmd = [str(venv_python), str(script_path)] + script_args

    # Run the script
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
