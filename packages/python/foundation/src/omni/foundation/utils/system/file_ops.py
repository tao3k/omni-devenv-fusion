"""
utils/file_ops.py
File operation utilities.

Protocol-based design.

Provides safe file read/write operations.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def read_file_safely(
    path: str, max_size: int = 100 * 1024, project_root: Path | None = None
) -> tuple[bool, str]:
    """Safely read a file within project boundaries.

    Args:
        path: File path relative to project root
        max_size: Maximum file size in bytes
        project_root: Project root directory

    Returns:
        Tuple of (success, content_or_error)
    """
    from .path_safety import is_safe_path

    is_safe, error_msg = is_safe_path(path, project_root)
    if not is_safe:
        return False, f"Error: {error_msg}"

    if project_root is None:
        from .path_safety import _default_project_root

        project_root = _default_project_root()

    full_path = project_root / path

    if not full_path.exists():
        return False, f"Error: File '{path}' does not exist"
    if not full_path.is_file():
        return False, f"Error: '{path}' is not a file"
    if full_path.stat().st_size > max_size:
        return False, f"Error: File '{path}' is too large (> {max_size // 1024}KB)"

    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
        return True, content
    except UnicodeDecodeError:
        return False, f"Error: Cannot read '{path}' - not a text file"
    except Exception as e:
        return False, f"Error reading file: {e}"


def write_file_safely(
    path: str,
    content: str,
    project_root: Path | None = None,
    create_backup: bool = True,
) -> tuple[bool, str]:
    """Safely write a file within project boundaries.

    Args:
        path: File path relative to project root
        content: Content to write
        project_root: Project root directory
        create_backup: Whether to create .bak backup

    Returns:
        Tuple of (success, message)
    """
    from .path_safety import is_safe_path

    is_safe, error_msg = is_safe_path(path, project_root)
    if not is_safe:
        return False, f"Error: {error_msg}"

    if project_root is None:
        from .path_safety import _default_project_root

        project_root = _default_project_root()

    full_path = project_root / path

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Error creating directory: {e}"

    # Create backup if file exists
    backup_info = ""
    if full_path.exists() and create_backup:
        backup_path = full_path.with_suffix(full_path.suffix + ".bak")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_backup = full_path.with_suffix(f"{full_path.suffix}.{timestamp}.bak")
        shutil.copy2(full_path, final_backup)
        backup_info = f" (backup: {final_backup.name})"

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"Successfully wrote {len(content)} bytes to '{path}'{backup_info}"
    except Exception as e:
        return False, f"Error writing file: {e}"


__all__ = ["read_file_safely", "write_file_safely"]
