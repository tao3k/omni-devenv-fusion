# mcp-core/instructions.py
"""
Project Instructions Loader - Eager Load at Session Start

Loads all instructions from agent/instructions/ at MCP server startup.
These are the DEFAULT PROMPTS that should be available to every LLM session.

Usage:
    from mcp_core.instructions import get_instructions, get_instruction
"""

from pathlib import Path

# Project root detection
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
instructions_dir = _PROJECT_ROOT / "agent" / "instructions"

# Lazy-loaded data
_data: dict[str, str] = {}
_loaded: bool = False
_lock_locked: bool = False  # Simple flag instead of Lock for this use case


def _ensure_loaded() -> None:
    """Load all instructions from agent/instructions/."""
    global _loaded, _lock_locked
    if _loaded:
        return
    if _lock_locked:
        # Already being loaded by another thread
        return
    _lock_locked = True
    try:
        if not instructions_dir.exists():
            _loaded = True
            return
        for md_file in instructions_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                name = md_file.stem
                _data[name] = content
            except Exception:
                continue
        _loaded = True
    finally:
        _lock_locked = False


def get_instructions() -> dict[str, str]:
    """Get all loaded instructions."""
    _ensure_loaded()
    return _data.copy()


def get_instruction(name: str) -> str | None:
    """Get a specific instruction by name."""
    _ensure_loaded()
    return _data.get(name)


def get_all_instructions_merged() -> str:
    """Get all instructions merged into a single string."""
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
    """List all available instruction names."""
    _ensure_loaded()
    return list(_data.keys())


def reload_instructions() -> None:
    """Force reload all instructions."""
    global _loaded, _data
    _loaded = False
    _data = {}
    _ensure_loaded()


# Eager load on first import
_ensure_loaded()

__all__ = [
    "get_instructions",
    "get_instruction",
    "get_all_instructions_merged",
    "list_instruction_names",
    "reload_instructions",
]
