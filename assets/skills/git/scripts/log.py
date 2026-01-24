"""
git/scripts/log.py - Git log operations
"""

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def get_log(n: int = 5) -> str:
    """Show recent commit history."""
    return _run(["git", "log", f"-n{n}", "--oneline"])


def get_log_detailed(n: int = 5) -> str:
    """Show recent commits with full details."""
    return _run(["git", "-n", str(n), "--pretty=format:%H%n%s%n%b%n---"])


def search_log(pattern: str, n: int = 20) -> str:
    """Search commit messages."""
    return _run(["git", "log", f"-n{n}", "--grep", pattern, "--oneline"])


def get_file_history(file_path: str, n: int = 10) -> str:
    """Show commit history for a specific file."""
    return _run(["git", "log", f"-n{n}", "--oneline", "--", file_path])
