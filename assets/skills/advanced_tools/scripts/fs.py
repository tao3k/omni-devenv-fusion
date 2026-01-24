"""
Advanced Filesystem Tools (Context Awareness)

Wraps visual structure tools to provide spatial awareness to the Agent.
"""

import shutil
import subprocess
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.advanced_tools.fs")


@skill_command(
    name="tree_view",
    description="""
    Generate a visual directory tree.

    Args:
        - directory: str = "." - Root directory
        - depth: int = 2 - How many levels to show
        - show_hidden: bool = false - Include hidden files
        - only_directories: bool = false - Show only directories
        - cmd: Optional[str] - Ignored (for compatibility)

    Returns:
        Tree structure or error if 'tree' not installed.
    """,
    autowire=True,
)
def tree_view(
    directory: str = ".",
    depth: int = 2,
    show_hidden: bool = False,
    only_directories: bool = False,
    paths: ConfigPaths | None = None,
    # Ignored - for compatibility
    cmd: str | None = None,
) -> dict[str, Any]:
    """
    Wraps 'tree' command for visual directory structure.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target = (root / directory).resolve()

    # Security Sandbox: Prevent escaping project root
    if not str(target).startswith(str(root)):
        return {"success": False, "error": "Access denied: Path outside project root."}

    tree_exec = shutil.which("tree")
    if not tree_exec:
        return {
            "success": False,
            "error": "'tree' command not found. Install via system package manager (e.g., brew install tree).",
        }

    cmd = [tree_exec]

    # Visual Options
    cmd.extend(["-L", str(depth)])  # Level
    cmd.append("--noreport")  # No summary footer

    if show_hidden:
        cmd.append("-a")
    else:
        # Standard noise filtering
        cmd.extend(["-I", ".git|__pycache__|node_modules|.venv|.DS_Store|target|dist|build"])

    if only_directories:
        cmd.append("-d")

    cmd.append(str(target))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        return {
            "success": True,
            "tool": "tree",
            "path": str(target.relative_to(root)),
            "output": result.stdout,
        }
    except Exception as e:
        logger.error(f"Tree view failed: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["tree_view"]
