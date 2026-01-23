"""
Advanced Filesystem Tools (Context Awareness)

Wraps visual structure tools to provide spatial awareness to the Agent.
"""

import subprocess
import shutil
from typing import Any
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.advanced_tools.fs")


@skill_command(
    name="tree_view",
    description="""
    Generate a visual directory tree structure.

    **Parameters**:
    - `directory` (required): Root directory to start tree from (default: `.`)
    - `depth` (optional, default: 2): How many directory levels to show
    - `show_hidden` (optional, default: false): Include hidden files starting with `.`
    - `only_directories` (optional, default: false): Show only directories, no files

    **Returns**: Visual tree representation or error if `tree` command not found.
    """,
    autowire=True,
)
def tree_view(
    directory: str = ".",
    depth: int = 2,
    show_hidden: bool = False,
    only_directories: bool = False,
    paths: ConfigPaths | None = None,
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
