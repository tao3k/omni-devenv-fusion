"""
common/skill_utils.py
Phase 35: Skill Utility Functions

Provides utilities for skill development:
- current_skill_dir: Get the current skill's root directory
- Skill path helpers for ODF-EP v7.0 structure

Usage:
    from common.skill_utils import current_skill_dir, skill_path

    # Get skill root directory
    skill_dir = current_skill_dir()

    # Build paths within skill structure
    backlog = skill_dir / "assets" / "Backlog.md"
    readme = skill_path("assets/guide.md")
"""

from pathlib import Path
from typing import Literal


def current_skill_dir() -> Path:
    """
    Get the current skill's root directory.

    Returns the directory containing the calling skill's tools.py.
    Useful for referencing skill-local resources (backlogs, assets, etc.).

    Example:
        from common.skill_utils import current_skill_dir

        # In assets/skills/git/tools.py:
        backlog = current_skill_dir() / "assets" / "Backlog.md"
        readme = current_skill_dir() / "references" / "readme.md"

    Returns:
        Path to the skill's root directory
    """
    # Get the directory of the caller's module (tools.py)
    # Walk up to find the skill root (parent of scripts/, references/, assets/)
    caller_frame = _get_caller_frame()
    caller_file = Path(caller_frame.filename)
    skill_dir = caller_file.parent

    # If tools.py is directly in skill root, return it
    # Otherwise, if called from a subdirectory, walk up
    while skill_dir.name not in ("scripts", "references", "assets", "data"):
        parent = skill_dir.parent
        if parent == skill_dir:
            break  # Reached root
        skill_dir = parent

    return skill_dir


def skill_path(
    relative_path: str,
    *,
    skill_dir: Path | None = None,
    _caller_file: str | None = None,
) -> Path:
    """
    Build a path within the ODF-EP v7.0 skill structure.

    Args:
        relative_path: Path relative to skill root (e.g., "assets/guide.md")
        skill_dir: Optional skill directory (uses caller's skill if not provided)
        _caller_file: Internal - file path of caller (for testing)

    Example:
        from common.skill_utils import skill_path

        # Automatic - detects skill from caller
        guide = skill_path("assets/guide.md")
        data = skill_path("data/config.json")

        # Explicit - for cases where detection fails
        guide = skill_path("assets/guide.md", skill_dir=Path("/path/to/skill"))

    Returns:
        Absolute Path to the resource
    """
    if skill_dir is None:
        if _caller_file:
            # Testing path
            skill_dir = Path(_caller_file).parent
        else:
            caller_frame = _get_caller_frame()
            # Handle different Python frame attribute names
            filename = getattr(caller_frame, "f_code", None)
            if filename:
                skill_dir = Path(filename.co_filename).parent
            else:
                # Fallback for older Python or different contexts
                skill_dir = Path(__file__).parent.parent / "skills"

    return skill_dir / relative_path


def skill_asset(relative_path: str, *, skill_dir: Path | None = None) -> Path:
    """
    Get path to a file in the skill's assets/ directory.

    Args:
        relative_path: Path relative to assets/ (e.g., "guide.md", "templates/config.json")
        skill_dir: Optional skill directory

    Example:
        from common.skill_utils import skill_asset

        guide = skill_asset("guide.md")
        template = skill_asset("templates/prompt.j2")

    Returns:
        Absolute Path to the asset
    """
    return skill_path(f"assets/{relative_path}", skill_dir=skill_dir)


def skill_command(relative_path: str, *, skill_dir: Path | None = None) -> Path:
    """
    Get path to a file in the skill's scripts/ directory.

    Args:
        relative_path: Path relative to scripts/ (e.g., "workflow.py", "utils.sh")
        skill_dir: Optional skill directory

    Example:
        from common.skill_utils import skill_command

        workflow = skill_command("workflow.py")
        script = skill_command("helpers.sh")

    Returns:
        Absolute Path to the script
    """
    return skill_path(f"scripts/{relative_path}", skill_dir=skill_dir)


def skill_reference(relative_path: str, *, skill_dir: Path | None = None) -> Path:
    """
    Get path to a file in the skill's references/ directory.

    Args:
        relative_path: Path relative to references/ (e.g., "docs.md", "architecture.md")
        skill_dir: Optional skill directory

    Example:
        from common.skill_utils import skill_reference

        doc = skill_reference("documentation.md")

    Returns:
        Absolute Path to the reference
    """
    return skill_path(f"references/{relative_path}", skill_dir=skill_dir)


def skill_data(relative_path: str, *, skill_dir: Path | None = None) -> Path:
    """
    Get path to a file in the skill's data/ directory.

    Args:
        relative_path: Path relative to data/ (e.g., "config.json", "data.csv")
        skill_dir: Optional skill directory

    Example:
        from common.skill_utils import skill_data

        config = skill_data("config.json")

    Returns:
        Absolute Path to the data file
    """
    return skill_path(f"data/{relative_path}", skill_dir=skill_dir)


# =============================================================================
# Internal Utilities
# =============================================================================


def _get_caller_frame():
    """Get the caller's stack frame (for path detection)."""
    import sys

    try:
        # Walk up the stack to find the caller (skip utility functions)
        frame = sys._getframe(2)  # Start 2 levels up (current + skill_path)

        # Skip our own utility functions
        frame = _skip_internal_frames(frame)

        return frame
    except Exception:
        # If frame inspection fails, return a dummy frame-like object
        return None


def _skip_internal_frames(frame):
    """Skip internal/utility function frames."""
    import sys

    while frame:
        code = getattr(frame, "f_code", None)
        if code is None:
            frame = getattr(frame, "f_back", None)
            continue

        filename = code.co_filename
        func_name = code.co_name

        # Skip if in this module or common package
        if "skill_utils" in filename:
            frame = getattr(frame, "f_back", None)
            continue

        # Skip private/internal functions
        if func_name.startswith("_"):
            frame = getattr(frame, "f_back", None)
            continue

        return frame

    return frame


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "current_skill_dir",
    "skill_path",
    "skill_asset",
    "skill_command",
    "skill_reference",
    "skill_data",
]
