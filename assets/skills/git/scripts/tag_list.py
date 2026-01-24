"""
git/scripts/tag_list.py - Git tag operations
"""

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def list_tags() -> str:
    """List all git tags."""
    return _run(["git", "tag", "-l"])


def create_tag(name: str, msg: str | None = None) -> str:
    """Create an annotated tag."""
    cmd = ["git", "tag"]
    if msg:
        cmd.extend(["-m", msg])
    cmd.append(name)
    return _run(cmd)


def delete_tag(name: str) -> str:
    """Delete a tag."""
    return _run(["git", "tag", "-d", name])


def get_tag_commit(tag: str) -> str:
    """Get the commit for a specific tag."""
    return _run(["git", "rev-parse", tag])
