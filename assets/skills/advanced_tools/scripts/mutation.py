"""
Advanced Mutation Tools (Stream Editing)

Wraps sed for efficient text transformation.
Focus: Speed and standard regex compliance.
"""

import subprocess
import shutil
import platform
from typing import Any
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.advanced_tools.mutation")


@skill_command(
    name="regex_replace",
    description="Replace text in a file using sed regex. Efficient for large files.",
    autowire=True,
)
def regex_replace(
    file_path: str,
    pattern: str,
    replacement: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Execute: sed -i 's/pattern/replacement/g' file
    Uses | as delimiter to avoid escaping path slashes.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target = (root / file_path).resolve()

    # 1. Security Check
    if not str(target).startswith(str(root)) or not target.exists():
        return {"success": False, "error": "Invalid file path."}

    # 2. Env Check
    sed_exec = shutil.which("sed")
    if not sed_exec:
        return {"success": False, "error": "'sed' not found."}

    # 3. Platform Handling (BSD/macOS vs GNU/Linux)
    is_macos = platform.system() == "Darwin"

    # Use extended regex (-r for GNU, -E for BSD) for better regex support
    ext_flag = "-E" if is_macos else "-r"

    # Construct sed expression with proper quoting
    # Use | as delimiter, assuming pattern/replacement don't contain it
    expr = f"s|{pattern}|{replacement}|g"

    # Build command: sed -i[ext] -e 'expr' file (BSD needs space after -i, GNU doesn't)
    cmd = [sed_exec, "-i" if not is_macos else "-i", ext_flag, expr, str(target)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {"success": False, "error": f"sed failed: {result.stderr}"}

        return {
            "success": True,
            "tool": "sed",
            "file": file_path,
            "command": " ".join(cmd),
        }
    except Exception as e:
        logger.error(f"Regex replace failed: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["regex_replace"]
