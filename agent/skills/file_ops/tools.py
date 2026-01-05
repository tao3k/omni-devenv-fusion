"""
File Operations Skill Tools
Migrated from src/mcp_server/coder/main.py
Provides file I/O, search, AST-based refactoring, and batch operations.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from common.mcp_core import is_safe_path, run_subprocess

# NOTE: polish_text is imported dynamically in save_file() to avoid cross-skill
# dependency issues at module load time. See save_file() for the implementation.


import structlog

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
# Pydantic Models for Batch Operations (Phase 24: MiniMax Style)
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
# Core File Operations
# =============================================================================


async def read_file(path: str) -> str:
    """
    Read a single file with line numbering.

    Use this when you only need one file, not the entire directory context.
    Much faster and cheaper (typically < 1k tokens vs 20k+ for full scan).
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    project_root = Path.cwd()
    full_path = project_root / path

    if not full_path.exists():
        return f"Error: File '{path}' does not exist."
    if not full_path.is_file():
        return f"Error: '{path}' is not a file."
    if full_path.stat().st_size > 100 * 1024:
        return f"Error: File '{path}' is too large (> 100KB)."

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        numbered_lines = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
        content = "".join(numbered_lines)
        return f"--- File: {path} ({len(lines)} lines) ---\n{content}"
    except UnicodeDecodeError:
        return f"Error: Cannot read '{path}' - not a text file."
    except Exception as e:
        return f"Error reading file: {e}"


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
            # Dynamic import to avoid cross-skill dependency at module load time
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

        # Build response with writing warnings if any
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


# =============================================================================
# Batch Operations (Phase 24: MiniMax Style)
# =============================================================================


async def apply_file_changes(changes: List[FileOperation]) -> str:
    """
    [BATCH] Efficiently apply changes to multiple files in one go.

    Use this for code generation or refactoring tasks to minimize tool calls
    and reduce permission confirmations.

    Args:
        changes: List of FileOperation objects specifying action, path, and content

    Returns:
        Markdown report of all changes made
    """
    project_root = Path.cwd()
    report = []
    success_count = 0
    error_count = 0

    for change in changes:
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

    # Build summary
    summary = f"**File Operations Summary**\n\n"
    summary += f"- Success: {success_count}\n"
    summary += f"- Errors: {error_count}\n\n"
    summary += "**Details:**\n" + "\n".join(report)

    return summary


# =============================================================================
# AST-Based Tools
# =============================================================================


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
    """
    Apply AST-based rewrite using ast-grep (async).

    This performs structural replacement, not text substitution.
    """
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


async def ast_search(pattern: str, lang: str = "py", path: str = ".") -> str:
    """
    Query code structure using ast-grep patterns.

    Use this for structural code search (e.g., "Find all functions calling API X").

    Pattern Examples (ast-grep syntax):
    - "def $NAME" - Find all function definitions
    - "async def $NAME" - Find all async functions
    - "if $COND:" - Find all if statements
    - "print($ARGS)" - Find print calls with any args
    - "import $MODULE" - Find all import statements
    - "class $NAME" - Class definitions (use class_def kind)
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_grep(pattern, lang, path)


async def ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    """
    Apply AST-based code rewrite using ast-grep.

    Use this for structural refactoring (e.g., "Replace all print statements with logger.info").

    CAUTION: This modifies files. Backups are recommended.

    Rewrite Examples:
    - pattern: "print($MSG)" -> replacement: "logger.info($MSG)"
    - pattern: "def $NAME($ARGS):" -> replacement: "async def $NAME($ARGS):"
    - pattern: "if $COND:" -> replacement: "if $COND:  # TODO: review condition"
    """
    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_rewrite(pattern, replacement, lang, path)


# =============================================================================
# Registration
# =============================================================================


def register(mcp: FastMCP):
    """Register File Operations tools using direct function binding."""
    import sys
    import importlib.util

    # Get the current module from sys.modules
    current_module = sys.modules.get("agent.skills.file_ops.tools")
    if current_module is None:
        spec = importlib.util.spec_from_file_location(
            "agent.skills.file_ops.tools",
            Path(__file__).resolve(),
        )
        current_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(current_module)
        sys.modules["agent.skills.file_ops.tools"] = current_module

    # Get functions from the module
    read_file_fn = getattr(current_module, "read_file", None)
    search_files_fn = getattr(current_module, "search_files", None)
    save_file_fn = getattr(current_module, "save_file", None)
    apply_changes_fn = getattr(current_module, "apply_file_changes", None)
    ast_search_fn = getattr(current_module, "ast_search", None)
    ast_rewrite_fn = getattr(current_module, "ast_rewrite", None)

    # Register tools directly
    if read_file_fn:
        mcp.add_tool(read_file_fn, "Read a single file with line numbering.")
    if search_files_fn:
        mcp.add_tool(search_files_fn, "Search for text patterns in files (like grep).")
    if save_file_fn:
        mcp.add_tool(save_file_fn, "Write content to a file within the project directory.")
    # Phase 24: Batch Operations (MiniMax Style)
    if apply_changes_fn:
        mcp.add_tool(
            apply_changes_fn,
            """[BATCH] Efficiently apply changes to multiple files in one go.

            Use this for code generation or refactoring tasks to minimize tool calls.
            Each change specifies: action (write/append), path, and content.

            Returns a Markdown report of all changes made.
            """,
        )
    if ast_search_fn:
        mcp.add_tool(ast_search_fn, "Query code structure using ast-grep patterns.")
    if ast_rewrite_fn:
        mcp.add_tool(ast_rewrite_fn, "Apply AST-based code rewrite using ast-grep.")

    logger.info("File Operations skill tools registered (Batch Mode enabled)")
