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
from typing import Any, Literal

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


def _json_result(success: bool, **kwargs) -> str:
    """Create JSON result with success flag and additional fields."""
    result = {"success": success}
    result.update(kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)


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
    """Read multiple files and return JSON."""
    if config_paths is None:
        config_paths = ConfigPaths()
    project_root: Path = config_paths.project_root  # type: ignore[assignment]

    if not paths:
        return _json_result(
            False, files=[], errors=[{"path": "", "message": "No files specified."}]
        )

    result: dict[str, Any] = {"files": [], "errors": []}

    for path in paths:
        if path.startswith("/"):
            is_safe, error_msg = is_safe_path(path, allow_absolute=True)
        else:
            is_safe, error_msg = is_safe_path(path, project_root=project_root)

        if not is_safe:
            result["errors"].append({"path": path, "message": error_msg})
            continue

        if path.startswith("/"):
            full_path = Path(path)
        else:
            full_path = project_root / path

        if not full_path.exists():
            result["errors"].append({"path": path, "message": "File does not exist."})
            continue
        if not full_path.is_file():
            result["errors"].append({"path": path, "message": "Not a file."})
            continue
        if full_path.stat().st_size > 100 * 1024:
            result["errors"].append({"path": path, "message": "File is too large (> 100KB)."})
            continue

        try:
            with open(full_path, encoding=encoding) as f:
                content = f.read()
            lines = content.splitlines()
            result["files"].append({"path": path, "lines": len(lines), "content": content})
        except UnicodeDecodeError:
            result["errors"].append({"path": path, "message": "Cannot read - not a text file."})
        except Exception as e:
            result["errors"].append({"path": path, "message": str(e)})

    return _json_result(len(result["errors"]) == 0, **result)


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
        return _json_result(False, path=path, error=error_msg)

    full_path = project_root / path

    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            return _json_result(False, path=path, error="Path is outside the project directory.")
    except Exception as e:
        return _json_result(False, path=path, error=f"Error resolving path: {e}")

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return _json_result(False, path=path, error=f"Error creating directory: {e}")

    backup_created = False
    if full_path.exists() and create_backup:
        backup_created = _create_backup(full_path)

    validation_error = None
    if validate_syntax:
        is_valid, error_msg = _validate_syntax(content, path)
        if not is_valid:
            validation_error = error_msg

    writing_warnings: list[dict[str, Any]] = []
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

    if validation_error:
        return _json_result(False, path=path, error=validation_error)

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return _json_result(
            True, path=path, bytes=len(content), backup=backup_created, warnings=writing_warnings
        )
    except Exception as e:
        return _json_result(False, path=path, error=str(e))


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

    operations: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

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
                errors.append({"path": change.path, "message": error_msg})
                continue

            full_path.parent.mkdir(parents=True, exist_ok=True)

            if change.action == "write":
                full_path.write_text(change.content, encoding="utf-8")
                operations.append(
                    {"path": change.path, "action": "write", "bytes": len(change.content)}
                )
            elif change.action == "append":
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(change.content)
                operations.append(
                    {"path": change.path, "action": "append", "bytes": len(change.content)}
                )
            elif change.action == "replace":
                if not full_path.exists():
                    raise FileNotFoundError(f"File not found: {change.path}")
                original_content = full_path.read_text(encoding="utf-8")
                if change.search_for:
                    new_content = original_content.replace(change.search_for, change.content)
                else:
                    new_content = change.content
                full_path.write_text(new_content, encoding="utf-8")
                operations.append(
                    {
                        "path": change.path,
                        "action": "replace",
                        "search_bytes": len(change.search_for),
                        "bytes": len(change.content),
                    }
                )

        except Exception as e:
            errors.append({"path": change.path, "message": str(e)})

    return _json_result(len(errors) == 0, operations=operations, errors=errors)


@skill_command(
    name="list_directory",
    category="view",
    description="""
    List files and directories at a path.

    Args:
        - path: str = "." - Directory path to list (use . for current directory, or relative path like src/)
        - type_filter: str = "all" - Filter: "all" (default), "f" (files only), "d" (directories only)

    Returns:
        When type_filter="all": list of items with name, type, size.
        When type_filter="f": list of all file paths.
        When type_filter="d": list of all directory paths.
    """,
    autowire=True,
)
async def list_directory(
    path: str = ".",
    type_filter: str = "all",
    paths: ConfigPaths | None = None,
) -> str:
    """List contents of a directory with optional type filtering."""
    if paths is None:
        paths = ConfigPaths()
    project_root: Path = paths.project_root  # type: ignore[assignment]

    try:
        target = (project_root / path).resolve()
        if not target.exists():
            return _json_result(False, path=path, error="Path does not exist.")
        if not target.is_dir():
            return _json_result(False, path=path, error="Path is not a directory.")

        if type_filter == "f":
            # Return all file paths
            files = []
            for item in target.rglob("*"):
                if item.is_file() and not item.name.startswith("."):
                    files.append(str(item.relative_to(project_root)))
            return _json_result(True, path=path, files=files)
        elif type_filter == "d":
            # Return all directory paths
            dirs = []
            for item in target.rglob("*"):
                if item.is_dir() and not item.name.startswith("."):
                    dirs.append(str(item.relative_to(project_root)))
            return _json_result(True, path=path, directories=dirs)
        else:
            # Return top-level items only
            items: list[dict[str, Any]] = []
            for item in target.iterdir():
                if item.name.startswith(".") and item.name != ".":
                    continue
                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
                if item.is_file():
                    item_info["size"] = item.stat().st_size
                items.append(item_info)
            return _json_result(True, path=path, items=items)
    except Exception as e:
        return _json_result(False, path=path, error=str(e))


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
        return _json_result(True, path=path, bytes=len(content))
    except Exception as e:
        return _json_result(False, path=path, error=str(e))


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
            return _json_result(False, path=path, error="File not found.")

        stat = target.stat()
        return _json_result(
            True,
            path=path,
            size=stat.st_size,
            type="directory" if target.is_dir() else "file",
            absolute=str(target),
        )
    except Exception as e:
        return _json_result(False, path=path, error=str(e))


__all__ = [
    "FileOperation",
    "apply_file_changes",
    "get_file_info",
    "list_directory",
    "read_files",
    "save_file",
    "write_file",
]
