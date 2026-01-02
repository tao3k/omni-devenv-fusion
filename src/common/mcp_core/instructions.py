# mcp-core/instructions.py
"""
Project Instructions Loader - Lazy Load

Loads all instructions from agent/instructions/ on first access.
Thread-safe and process-fork-safe implementation.

Key Design:
- Pure lazy loading: No I/O on import, avoids fork deadlock
- Double-checked locking: Fast path after first load
- thread-safe with Lock: No race conditions or empty data

Uses GitOps via common.mcp_core.project_root for path detection.

Usage:
    from mcp_core.instructions import get_instructions, get_instruction

    # First call triggers lazy load
    all_instructions = get_instructions()
"""

from pathlib import Path
import threading

# Project root detection using GitOps
from common.mcp_core.gitops import get_project_root, get_instructions_dir

_PROJECT_ROOT = get_project_root()
instructions_dir = get_instructions_dir()

# Internal state
_data: dict[str, str] = {}
_loaded: bool = False
_lock = threading.Lock()


def _load_data_internal() -> None:
    """Internal function to perform the actual file reading.

    Assumes the lock is already held by the caller.
    """
    global _data, _loaded

    # Double-check after acquiring lock
    if _loaded:
        return

    temp_data = {}
    if instructions_dir.exists():
        for md_file in instructions_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                name = md_file.stem
                temp_data[name] = content
            except Exception:
                continue

    _data = temp_data
    _loaded = True


def _ensure_loaded() -> None:
    """Ensure instructions are loaded in a thread-safe manner.

    Uses double-checked locking pattern:
    1. Fast path: Check _loaded without lock (most calls)
    2. Slow path: Acquire lock and load if needed (first call)
    """
    # Fast path: Already loaded
    if _loaded:
        return

    # Slow path: Acquire lock and load
    with _lock:
        _load_data_internal()


def get_instructions() -> dict[str, str]:
    """Get all loaded instructions.

    Returns:
        Dictionary mapping instruction name to content.
    """
    _ensure_loaded()
    return _data.copy()


def get_instruction(name: str) -> str | None:
    """Get a specific instruction by name.

    Args:
        name: Instruction name (without .md extension), e.g., "project-conventions"

    Returns:
        Instruction content or None if not found.
    """
    _ensure_loaded()
    return _data.get(name)


def get_all_instructions_merged() -> str:
    """Get all instructions merged into a single string.

    This is useful for injecting into LLM system prompts.

    Returns:
        Merged instruction string.
    """
    _ensure_loaded()
    if not _data:
        return ""
    merged = []
    for name in sorted(_data.keys()):
        merged.append(f"# {name.replace('-', ' ').title()}")
        merged.append(_data[name])
        merged.append("")
    return "\n".join(merged)


def list_instruction_names() -> list[str]:
    """List all available instruction names.

    Returns:
        List of instruction file names (without .md extension).
    """
    _ensure_loaded()
    return list(_data.keys())


def reload_instructions() -> None:
    """Force reload all instructions.

    Use this for testing or after adding new instruction files.
    """
    global _loaded
    with _lock:
        _loaded = False
        _load_data_internal()


# NOTE: No eager loading at import time!
# This avoids fork deadlock issues with threading.Lock.
# All loading is deferred to first access.

__all__ = [
    "get_instructions",
    "get_instruction",
    "get_all_instructions_merged",
    "list_instruction_names",
    "reload_instructions",
]
