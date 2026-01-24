"""
git/scripts/remote.py - Git remote operations
"""

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def list_remotes() -> str:
    """Show remote repositories."""
    return _run(["git", "remote", "-v"])


def get_remote_url(remote_name: str = "origin") -> str:
    """Get URL for a specific remote."""
    return _run(["git", "remote", "get-url", remote_name])


def add_remote(name: str, url: str) -> str:
    """Add a remote repository."""
    return _run(["git", "remote", "add", name, url])


def remove_remote(name: str) -> str:
    """Remove a remote."""
    return _run(["git", "remote", "remove", name])


def set_remote_url(name: str, url: str) -> str:
    """Set remote URL."""
    return _run(["git", "remote", "set-url", name, url])
