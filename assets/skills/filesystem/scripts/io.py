"""
filesystem/scripts/io.py - File I/O Operations

Modernized:
- @skill_command with autowire=True for clean dependency injection
- ConfigPaths for security-constrained file operations within project_root
- Path traversal protection using is_safe_path

NOTE: This skill is for FILE I/O operations ONLY.
For text search, use: advanced_search.search_project_code (ripgrep)
For AST search, use: code_navigation.search_code (AST patterns)
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.utils.system import is_safe_path

logger = get_logger("skill.filesystem")

_ALLOWED_HIDDEN_FILES = {
    ".gitignore",
    ".clang-format",
    ".prettierrc",
    ".markdownlintrc",
    ".editorconfig",
    ".gitattributes",
    ".dockerignore",
}


class FileOperation(BaseModel):
    """Single file operation for batch processing."""

    action: Literal["write", "append", "replace"] = Field(
        ..., description="Action: write (create/overwrite), append, or replace (search/replace)"
    )
    path: str = Field(..., description="Relative path to file")
    content: str = Field(..., description="Content to write, append, or new content for replace")
    search_for: str = Field("", description="Text to search for (only for replace action)")


def _validate_syntax(content: str, filepath: str) -> tuple[bool, str]:
    """Validate syntax for Python and Nix files."""
    if filepath.endswith(".py"):
        try:
            import ast

            ast.parse(content)
            return True, ""
        except SyntaxError as e:
            return False, f"Python syntax error at line {e.lineno}: {e.msg}"

    if filepath.endswith(".nix"):
        try:
            process = subprocess.run(
                ["nix-instantiate", "--parse", "-"],
                input=content,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if process.returncode != 0:
                return False, f"Nix syntax error: {process.stderr.strip()}"
            return True, ""
        except FileNotFoundError:
            return True, ""
        except subprocess.TimeoutExpired:
            return True, ""

    return True, ""


def _create_backup(filepath: Path) -> bool:
    """Create a .bak backup of existing file."""
    try:
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        shutil.copy2(filepath, backup_path)
        return True
    except Exception:
        return False


@skill_command(
    name="read_files",
    category="read",
    description="""
    Read file(s) with line numbers.

    Args:
        - paths: list[str] - List of file paths to read. Supports project-relative paths (e.g., src/main.py) or trusted absolute paths (required)
        - encoding: str = utf-8 - File encoding for all files

    Returns:
        Combined content from all files with file headers and line numbers.
        Errors are reported inline for each file.
    """,
    autowire=True,
)
def read_files(
    paths: list[str],
    encoding: str = "utf-8",
    config_paths: ConfigPaths | None = None,
) -> str:
    """Read multiple files and combine results."""
    if config_paths is None:
        config_paths = ConfigPaths()
    project_root: Path = config_paths.project_root  # type: ignore[assignment]

    if not paths:
        return "No files specified."

    results = []
    success_count = 0
    error_count = 0

    for path in paths:
        # Validate path
        if path.startswith("/"):
            is_safe, error_msg = is_safe_path(path, allow_absolute=True)
        else:
            is_safe, error_msg = is_safe_path(path, project_root=project_root)

        if not is_safe:
            results.append(f"--- File: {path} ---\nError: {error_msg}")
            error_count += 1
            continue

        if path.startswith("/"):
            full_path = Path(path)
        else:
            full_path = project_root / path

        if not full_path.exists():
            results.append(f"--- File: {path} ---\nError: File does not exist.")
            error_count += 1
            continue
        if not full_path.is_file():
            results.append(f"--- File: {path} ---\nError: Not a file.")
            error_count += 1
            continue
        if full_path.stat().st_size > 100 * 1024:
            results.append(f"--- File: {path} ---\nError: File is too large (> 100KB).")
            error_count += 1
            continue

        try:
            with open(full_path, encoding=encoding) as f:
                lines = f.readlines()
            numbered_lines = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
            content = "".join(numbered_lines)
            results.append(f"--- File: {path} ({len(lines)} lines) ---\n{content}")
            success_count += 1
        except UnicodeDecodeError:
            results.append(f"--- File: {path} ---\nError: Cannot read - not a text file.")
            error_count += 1
        except Exception as e:
            results.append(f"--- File: {path} ---\nError: {e}")
            error_count += 1

    # Add summary
    summary = f"\n--- Summary: {success_count} files read, {error_count} errors ---\n"
    return "\n".join(results) + summary


@skill_command(
    name="save_file",
    category="write",
    description="""
    Writes content to a file within the project directory.

    Features:
    - Auto-creates .bak backup before overwriting (safe rollback)
    - Syntax validation for Python and Nix files
    - Auto-writing-check for markdown files (check style + structure)
    - Security checks for path safety

    Args:
        - path: str - Relative path to the file (required)
        - content: str - Content to write (required)
        - create_backup: bool = true - If true, creates .bak backup
        - validate_syntax: bool = true - If true, validates Python/Nix syntax
        - auto_check_writing: bool = true - If true, runs writer checks on .md files

    Returns:
        Success message with byte count, or error message.
    """,
    autowire=True,
)
async def save_file(
    path: str,
    content: str,
    create_backup: bool = True,
    validate_syntax: bool = True,
    auto_check_writing: bool = True,
    paths: ConfigPaths | None = None,
) -> str:
    """Write content to a file within the project."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    is_safe, error_msg = is_safe_path(
        path,
        project_root=project_root,
        allow_hidden=False,
        allowed_hidden_files=_ALLOWED_HIDDEN_FILES,
    )
    if not is_safe:
        return f"Error: {error_msg}"

    full_path = project_root / path

    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            return "Error: Path is outside the project directory."
    except Exception as e:
        return f"Error resolving path: {e}"

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"Error creating directory: {e}"

    backup_info = ""
    if full_path.exists() and create_backup:
        if _create_backup(full_path):
            backup_info = " (backup: .bak file created)"

    if validate_syntax:
        is_valid, error_msg = _validate_syntax(content, path)
        if not is_valid:
            return f"Error: Syntax validation failed\n{error_msg}"

    writing_warnings = []
    if auto_check_writing and path.endswith(".md"):
        try:
            from ..writer.scripts.text import polish_text

            polish_result = await polish_text(content)
            polish_data = json.loads(polish_result)
            violations = polish_data.get("violations", [])
            if violations:
                writing_warnings = violations
        except Exception:
            pass

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        response_parts = [f"Successfully wrote {len(content)} bytes to '{path}'{backup_info}"]

        if writing_warnings:
            response_parts.append("\nWriting Style Warnings (auto-checked):")
            type_counts = {}
            for v in writing_warnings:
                t = v.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            for vtype, count in type_counts.items():
                response_parts.append(f"  - {vtype}: {count} issue(s)")
            response_parts.append("  Run writer.polish_text for details.")

        return "\n".join(response_parts)
    except Exception as e:
        return f"Error writing file: {e}"


@skill_command(
    name="apply_changes",
    category="write",
    description="""
    [BATCH] Efficiently applies changes to multiple files in one go.

    Use this for code generation or refactoring tasks to minimize tool calls and reduce permission confirmations.

    Args:
        - changes: List[FileOperation] - List of file operations with action (write, append, replace), path, and content (required)

    Returns:
        Summary of successful and failed operations with details.
    """,
    autowire=True,
)
async def apply_file_changes(
    changes: list[FileOperation],
    paths: ConfigPaths | None = None,
) -> str:
    """Apply multiple file changes in one operation."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    report = []
    success_count = 0
    error_count = 0

    for change in changes:
        if isinstance(change, dict):
            change = FileOperation(**change)

        try:
            full_path = project_root / change.path

            is_safe, error_msg = is_safe_path(
                change.path,
                project_root=project_root,
                allow_hidden=False,
                allowed_hidden_files=_ALLOWED_HIDDEN_FILES,
            )
            if not is_safe:
                report.append(f"- `{change.path}`: {error_msg}")
                error_count += 1
                continue

            full_path.parent.mkdir(parents=True, exist_ok=True)

            if change.action == "write":
                full_path.write_text(change.content, encoding="utf-8")
                report.append(f"- **Wrote**: `{change.path}` ({len(change.content)} bytes)")
            elif change.action == "append":
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(change.content)
                report.append(f"- **Appended**: `{change.path}` ({len(change.content)} bytes)")
            elif change.action == "replace":
                if not full_path.exists():
                    raise FileNotFoundError(f"File not found: {change.path}")
                original_content = full_path.read_text(encoding="utf-8")
                if change.search_for:
                    new_content = original_content.replace(change.search_for, change.content)
                else:
                    new_content = change.content
                full_path.write_text(new_content, encoding="utf-8")
                report.append(
                    f"- **Replaced**: `{change.path}` ({len(change.search_for)} chars -> {len(change.content)} chars)"
                )

            success_count += 1

        except Exception as e:
            report.append(f"- **Failed**: `{change.path}` - {e!s}")
            error_count += 1

    summary = "**File Operations Summary**\n\n"
    summary += f"- Success: {success_count}\n"
    summary += f"- Errors: {error_count}\n\n"
    summary += "**Details:**\n" + "\n".join(report)

    return summary


@skill_command(
    name="list_directory",
    category="view",
    description="""
    List files and directories at a path.

    Args:
        - path: str = "." - Directory path to list (use . for current directory, or relative path like src/)

    Returns:
        Formatted listing with file/directory type and size.
    """,
    autowire=True,
)
async def list_directory(
    path: str = ".",
    paths: ConfigPaths | None = None,
) -> str:
    """List contents of a directory."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    try:
        target = (project_root / path).resolve()
        if not target.exists():
            return f"Path does not exist: {path}"
        if not target.is_dir():
            return f"Path is not a directory: {path}"

        items = []
        for item in target.iterdir():
            if item.name.startswith(".") and item.name != ".":
                continue
            kind = "DIR " if item.is_dir() else "FILE"
            size = "-" if item.is_dir() else f"{item.stat().st_size}b"
            items.append(f"{kind:<5} {size:<10} {item.name}")

        return f"Directory Listing for '{path}':\n" + "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing directory: {e}"


@skill_command(
    name="write_file",
    category="write",
    description="""
    Creates or overwrites a file with new content.

    Simple file write without backup or validation. Use save_file for safer write with backup support.

    Args:
        - path: str - Relative path to the file (required)
        - content: str - Content to write (required)

    Returns:
        Success message with byte count, or error message.
    """,
    autowire=True,
)
async def write_file(
    path: str,
    content: str,
    paths: ConfigPaths | None = None,
) -> str:
    """Simple file write operation."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    try:
        target = (project_root / path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@skill_command(
    name="get_file_info",
    category="view",
    description="""
    Gets metadata about a file.

    Args:
        - path: str - Path to the file or directory (required)

    Returns:
        File/directory information including path, size, type, and absolute path.
    """,
    autowire=True,
)
async def get_file_info(
    path: str,
    paths: ConfigPaths | None = None,
) -> str:
    """Get metadata about a file or directory."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    try:
        target = (project_root / path).resolve()
        if not target.exists():
            return "File not found."
        stat = target.stat()
        return (
            f"Path: {path}\n"
            f"Size: {stat.st_size} bytes\n"
            f"Type: {'Directory' if target.is_dir() else 'File'}\n"
            f"Absolute: {target}"
        )
    except Exception as e:
        return f"Error: {e}"


__all__ = [
    "FileOperation",
    "apply_file_changes",
    "get_file_info",
    "list_directory",
    "read_files",
    "save_file",
    "write_file",
]
