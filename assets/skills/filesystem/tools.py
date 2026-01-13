"""
agent/skills/filesystem/tools.py
Filesystem Skill - Safe File Operations (Phase 36).

Consolidated from file_ops:
- read_file (with line numbers)
- grep_search (text search)
- save_file (with backup + validation)
- apply_changes (batch operations)
- ast_search, ast_rewrite (AST-based)

Plus retained from original filesystem:
- list_directory
- write_file
- get_file_info
"""

import fnmatch
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Literal, Any

from pydantic import BaseModel, Field
from common.mcp_core import is_safe_path, run_subprocess
import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# Safe hidden files that are allowed
_ALLOWED_HIDDEN_FILES = {
    ".gitignore",
    ".clang-format",
    ".prettierrc",
    ".markdownlintrc",
    ".editorconfig",
    ".gitattributes",
    ".dockerignore",
}


# =============================================================================
# Pydantic Models for Batch Operations
# =============================================================================


class FileOperation(BaseModel):
    """Single file operation for batch processing."""

    action: Literal["write", "append"] = Field(
        ..., description="Action to perform: write (create/overwrite) or append"
    )
    path: str = Field(..., description="Relative path to file")
    content: str = Field(..., description="Content to write or append")


# =============================================================================
# Utility Functions
# =============================================================================


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


# =============================================================================
# File Operations (from file_ops)
# =============================================================================


@skill_command(
    name="read_file",
    category="read",
    description="Read a single file with line numbering.",
)
async def read_file(file_path: str) -> str:
    """
    Read a single file with line numbering.

    Supports:
    - Project-relative paths (e.g., "src/main.py")
    - Trusted absolute paths (e.g., /nix/store/*)
    """
    # Check for trusted absolute paths (e.g., /nix/store/*)
    if file_path.startswith("/"):
        is_safe, error_msg = is_safe_path(file_path, allow_absolute=True)
    else:
        is_safe, error_msg = is_safe_path(file_path)

    if not is_safe:
        return f"Error: {error_msg}"

    # Handle absolute paths (trusted) vs relative paths
    if file_path.startswith("/"):
        full_path = Path(file_path)
    else:
        project_root = Path.cwd()
        full_path = project_root / file_path

    if not full_path.exists():
        return f"Error: File '{file_path}' does not exist."
    if not full_path.is_file():
        return f"Error: '{file_path}' is not a file."
    if full_path.stat().st_size > 100 * 1024:
        return f"Error: File '{file_path}' is too large (> 100KB)."

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        numbered_lines = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
        content = "".join(numbered_lines)
        return f"--- File: {file_path} ({len(lines)} lines) ---\n{content}"
    except UnicodeDecodeError:
        return f"Error: Cannot read '{file_path}' - not a text file."
    except Exception as e:
        return f"Error reading file: {e}"


@skill_command(
    name="search_files",
    category="read",
    description="Search for text patterns in files (grep-style).",
)
async def search_files(pattern: str, path: str = ".", use_regex: bool = False) -> str:
    """
    Search for text patterns in files (like grep).

    Use this to find code snippets, function definitions, or specific patterns.
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    project_root = Path.cwd()
    search_root = project_root / path

    if not search_root.exists() or not search_root.is_dir():
        return f"Error: Directory '{path}' does not exist."

    try:
        flags = re.IGNORECASE if not use_regex else re.IGNORECASE | re.MULTILINE
        regex = re.compile(pattern, flags) if use_regex else None

        matches = []
        max_matches = 100

        for root, dirs, files in os.walk(search_root):
            # Skip hidden and cache directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".cache"]
            files = [f for f in files if not f.startswith(".")]

            for filename in files:
                filepath = Path(root) / filename
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if len(matches) >= max_matches:
                                break
                            if use_regex:
                                if regex.search(line):
                                    matches.append(
                                        f"{filepath.relative_to(project_root)}:{i}: {line.rstrip()}"
                                    )
                            else:
                                if pattern.lower() in line.lower():
                                    matches.append(
                                        f"{filepath.relative_to(project_root)}:{i}: {line.rstrip()}"
                                    )
                except Exception:
                    continue

            if len(matches) >= max_matches:
                break

        if not matches:
            return f"No matches found for '{pattern}' in '{path}'"

        result = f"--- Search Results: '{pattern}' in {path} ---\n"
        result += f"Found {len(matches)} matches:\n\n"
        result += "\n".join(matches[:max_matches])
        if len(matches) >= max_matches:
            result += f"\n... (showing first {max_matches} matches)"
        return result

    except re.error as e:
        return f"Error: Invalid regex pattern - {e}"
    except Exception as e:
        return f"Error searching: {e}"


@skill_command(
    name="save_file",
    category="write",
    description="Write content to a file with backup and validation.",
)
async def save_file(
    path: str,
    content: str,
    create_backup: bool = True,
    validate_syntax: bool = True,
    auto_check_writing: bool = True,
) -> str:
    """
    Write content to a file within the project directory.

    Features:
    - Auto-creates .bak backup before overwriting (safe rollback)
    - Syntax validation for Python and Nix files
    - Auto-writing-check for .md files (check style + structure)
    - Security checks for path safety
    """
    is_safe, error_msg = is_safe_path(
        path,
        allow_hidden=False,
        allowed_hidden_files=_ALLOWED_HIDDEN_FILES,
    )
    if not is_safe:
        return f"Error: {error_msg}"

    project_root = Path.cwd()
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

    # Auto-writing-check for markdown files
    writing_warnings = []
    if auto_check_writing and path.endswith(".md"):
        try:
            from agent.skills.writer.tools import polish_text

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
    description="Apply changes to multiple files in one go.",
)
async def apply_file_changes(changes: List[FileOperation]) -> str:
    """
    [BATCH] Efficiently apply changes to multiple files in one go.

    Use this for code generation or refactoring tasks to minimize tool calls
    and reduce permission confirmations.
    """
    project_root = Path.cwd()
    report = []
    success_count = 0
    error_count = 0

    for change in changes:
        # Handle both FileOperation objects and raw dicts from MCP
        if isinstance(change, dict):
            change = FileOperation(**change)

        try:
            full_path = project_root / change.path

            # Validate path safety
            is_safe, error_msg = is_safe_path(
                change.path,
                allow_hidden=False,
                allowed_hidden_files=_ALLOWED_HIDDEN_FILES,
            )
            if not is_safe:
                report.append(f"- ❌ `{change.path}`: {error_msg}")
                error_count += 1
                continue

            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if change.action == "write":
                full_path.write_text(change.content, encoding="utf-8")
                report.append(f"- ✅ **Wrote**: `{change.path}` ({len(change.content)} bytes)")
            elif change.action == "append":
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(change.content)
                report.append(f"- ➕ **Appended**: `{change.path}` ({len(change.content)} bytes)")

            success_count += 1

        except Exception as e:
            report.append(f"- ❌ **Failed**: `{change.path}` - {str(e)}")
            error_count += 1

    summary = f"**File Operations Summary**\n\n"
    summary += f"- Success: {success_count}\n"
    summary += f"- Errors: {error_count}\n\n"
    summary += "**Details:**\n" + "\n".join(report)

    return summary


async def _run_ast_grep(pattern: str, lang: str = "py", search_path: str = ".") -> str:
    """Run ast-grep query and returns matches (async)."""
    returncode, stdout, stderr = await run_subprocess(
        "ast-grep", ["run", "-p", pattern, "-l", lang, search_path], timeout=30
    )

    if returncode != 0 and "no matches" not in stderr.lower():
        return f"Error: ast-grep failed\nstderr: {stderr}"

    if not stdout.strip():
        return f"No matches found for pattern: {pattern}"

    return f"--- ast-grep Results: {pattern} ---\n{stdout}"


async def _run_ast_rewrite(
    pattern: str, replacement: str, lang: str = "py", search_path: str = "."
) -> str:
    """Apply AST-based rewrite using ast-grep (async)."""
    returncode, stdout, stderr = await run_subprocess(
        "ast-grep",
        ["run", "-p", pattern, "-r", replacement, "-l", lang, search_path, "--update-all"],
        timeout=30,
    )

    # ast-grep returns exit code 1 when no matches found (not an error)
    if returncode == 1 and not stdout.strip() and not stderr.strip():
        return f"No matches found for pattern: {pattern}"

    if returncode != 0:
        return f"Error: ast-rewrite failed\nstderr: {stderr}"

    return f"--- ast-rewrite Applied ---\n{stdout}"


@skill_command(
    name="ast_search",
    category="read",
    description="Query code structure using ast-grep patterns.",
)
async def ast_search(pattern: str, lang: str = "py", path: str = ".") -> str:
    """
    Query code structure using ast-grep patterns.

    Pattern Examples (ast-grep syntax):
    - "def $NAME" - Find all function definitions
    - "async def $NAME" - Find all async functions
    - "if $COND:" - Find all if statements
    - "print($ARGS)" - Find print calls with any args
    - "import $MODULE" - Find all import statements
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_grep(pattern, lang, path)


@skill_command(
    name="ast_rewrite",
    category="write",
    description="Apply AST-based code rewrite using ast-grep.",
)
async def ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    """
    Apply AST-based code rewrite using ast-grep.

    Rewrite Examples:
    - pattern: "print($MSG)" -> replacement: "logger.info($MSG)"
    - pattern: "def $NAME($ARGS):" -> replacement: "async def $NAME($ARGS):"
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_rewrite(pattern, replacement, lang, path)


# =============================================================================
# Retained from Original Filesystem
# =============================================================================


@skill_command(
    name="list_directory",
    category="read",
    description="List files and directories in the given path.",
)
async def list_directory(path: str = ".") -> str:
    """List files and directories in the given path."""
    try:
        base = Path.cwd()
        target = (base / path).resolve()
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
    description="Create or Overwrite a file with new content.",
)
async def write_file(path: str, content: str) -> str:
    """Create or Overwrite a file with new content."""
    try:
        base = Path.cwd()
        target = (base / path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@skill_command(
    name="get_file_info",
    category="read",
    description="Get metadata about a file.",
)
async def get_file_info(path: str) -> str:
    """Get metadata about a file."""
    try:
        base = Path.cwd()
        target = (base / path).resolve()
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
