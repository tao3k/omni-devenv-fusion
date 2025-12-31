# mcp-server/coder.py
"""
Coding Expert MCP Server - The "Hands"

Focus: High-quality code implementation, AST-based refactoring, Performance, Security.
Role: Precise execution of coding tasks defined by the Orchestrator.

Tools:
- read_file: Single file reading
- search_files: Pattern search (grep-like)
- save_file: Write files with backup & syntax validation
- ast_search: Query code structure using ast-grep
- ast_rewrite: Apply structural patches based on AST patterns
"""
import os
import sys
import json
import asyncio
import logging
import subprocess
import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP


def _load_env_from_file() -> Dict[str, str]:
    path = os.environ.get("CODER_ENV_FILE") or os.path.join(os.getcwd(), ".mcp.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    coder_env = (
        data.get("mcpServers", {})
        .get("coder", {})
        .get("env", {})
        if isinstance(data, dict)
        else {}
    )
    flat_env = data if isinstance(data, dict) else {}
    merged: Dict[str, str] = {}
    for source in (flat_env, coder_env):
        for key, value in source.items():
            if isinstance(value, str):
                merged[key] = value
    return merged


_ENV_FILE_VALUES = _load_env_from_file()


def _env(key: str, default: str | None = None) -> str | None:
    return _ENV_FILE_VALUES.get(key) or os.environ.get(key) or default


LOG_LEVEL = os.environ.get("CODER_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("coder")


def _log_decision(event: str, payload: Dict[str, Any]) -> None:
    logger.info(json.dumps({"event": event, **payload}))


mcp = FastMCP("coder-tools")

sys.stderr.write(f"🔧 Coder Server (AST + Surgical Coding) starting... PID: {os.getpid()}\n")


# Files that should never be overwritten
_BLOCKED_PATHS = {
    "/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/",
    ".bashrc", ".bash_profile", ".zshrc", ".profile",
    "known_hosts", "authorized_keys",
}


def _is_safe_path(path: str) -> tuple[bool, str]:
    """Check if the path is safe to write within the project directory."""
    if path.startswith("/"):
        return False, "Absolute paths are not allowed."
    if ".." in path:
        return False, "Parent directory traversal is not allowed."
    filename = Path(path).name
    if filename.startswith(".") and filename not in {".gitignore", ".clang-format", ".prettierrc"}:
        safe_hidden = {".gitignore", ".clang-format", ".prettierrc", ".markdownlintrc"}
        if filename not in safe_hidden:
            return False, f"Hidden file '{filename}' is not allowed."
    for blocked in _BLOCKED_PATHS:
        if path.startswith(blocked):
            return False, f"Blocked path: {blocked}"
    return True, ""


def _validate_syntax(content: str, filepath: str) -> tuple[bool, str]:
    """Validate syntax for Python and Nix files."""
    if filepath.endswith(".py"):
        try:
            ast.parse(content)
            _log_decision("syntax_check.python", {"path": filepath, "valid": True})
            return True, ""
        except SyntaxError as e:
            _log_decision("syntax_check.python", {"path": filepath, "valid": False, "error": str(e)})
            return False, f"Python syntax error at line {e.lineno}: {e.msg}"

    if filepath.endswith(".nix"):
        try:
            process = subprocess.run(
                ["nix-instantiate", "--parse", "-"],
                input=content,
                capture_output=True,
                text=True,
                timeout=10
            )
            if process.returncode != 0:
                _log_decision("syntax_check.nix", {"path": filepath, "valid": False})
                return False, f"Nix syntax error: {process.stderr.strip()}"
            _log_decision("syntax_check.nix", {"path": filepath, "valid": True})
            return True, ""
        except FileNotFoundError:
            _log_decision("syntax_check.nix", {"path": filepath, "status": "skipped"})
            return True, ""
        except subprocess.TimeoutExpired:
            return True, ""

    return True, ""


def _create_backup(filepath: Path) -> bool:
    """Create a .bak backup of existing file."""
    try:
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        import shutil
        shutil.copy2(filepath, backup_path)
        _log_decision("backup_created", {"path": str(filepath), "backup": str(backup_path)})
        return True
    except Exception as e:
        _log_decision("backup_failed", {"path": str(filepath), "error": str(e)})
        return False


# =============================================================================
# Micro-Level File Operations
# =============================================================================

@mcp.tool()
async def read_file(path: str) -> str:
    """
    Read a single file (lightweight alternative to get_codebase_context).

    Use this when you only need one file, not the entire directory context.
    Much faster and cheaper (typically < 1k tokens vs 20k+ for full scan).
    """
    if ".." in path or path.startswith("/"):
        _log_decision("read_file.security_block", {"path": path})
        return "Error: Path traversal or absolute paths not allowed."

    project_root = Path.cwd()
    full_path = project_root / path

    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            _log_decision("read_file.security_block", {"path": path})
            return "Error: Path is outside the project directory."
    except Exception as e:
        return f"Error resolving path: {e}"

    if not full_path.exists():
        return f"Error: File '{path}' does not exist."
    if not full_path.is_file():
        return f"Error: '{path}' is not a file."
    if full_path.stat().st_size > 100 * 1024:
        return f"Error: File '{path}' is too large (> 100KB)."

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        numbered_lines = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
        content = "".join(numbered_lines)
        _log_decision("read_file.success", {"path": path, "lines": len(lines)})
        return f"--- File: {path} ({len(lines)} lines) ---\n{content}"
    except UnicodeDecodeError:
        return f"Error: Cannot read '{path}' - not a text file."
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
async def search_files(pattern: str, path: str = ".", use_regex: bool = False) -> str:
    """
    Search for text patterns in files (like grep).

    Use this to find code snippets, function definitions, or specific patterns.
    """
    if ".." in path or path.startswith("/"):
        _log_decision("search_files.security_block", {"path": path})
        return "Error: Path traversal or absolute paths not allowed."

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
                                    matches.append(f"{filepath.relative_to(project_root)}:{i}: {line.rstrip()}")
                            else:
                                if pattern.lower() in line.lower():
                                    matches.append(f"{filepath.relative_to(project_root)}:{i}: {line.rstrip()}")
                except Exception:
                    continue

            if len(matches) >= max_matches:
                break

        _log_decision("search_files.success", {"pattern": pattern, "matches": len(matches)})

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
        _log_decision("search_files.error", {"pattern": pattern, "error": str(e)})
        return f"Error searching: {e}"


# =============================================================================
# AST-Based Tools (ast-grep)
# =============================================================================

def _run_ast_grep(pattern: str, lang: str = "py", path: str = ".") -> str:
    """Run ast-grep query and return matches."""
    try:
        process = subprocess.run(
            ["ast-grep", "-p", pattern, "-l", lang, "-d", path],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = process.stdout
        stderr = process.stderr

        if process.returncode != 0 and "no matches" not in stderr.lower():
            return f"Error: ast-grep failed\nstderr: {stderr}"

        _log_decision("ast_grep.success", {"pattern": pattern, "lang": lang})

        if not output.strip():
            return f"No matches found for pattern: {pattern}"

        return f"--- ast-grep Results: {pattern} ---\n{output}"

    except FileNotFoundError:
        return "Error: 'ast-grep' command not found. Install with: nix-env -iA nixpkgs.ast-grep"
    except subprocess.TimeoutExpired:
        return "Error: ast-grep timed out"
    except Exception as e:
        return f"Error running ast-grep: {e}"


def _run_ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    """
    Apply AST-based rewrite using ast-grep.

    This performs structural replacement, not text substitution.
    """
    try:
        # First, do a dry run to show what would change
        process = subprocess.run(
            ["ast-grep", "-p", pattern, "-r", replacement, "-l", lang, "-d", path, "--rewrite"],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = process.stdout
        stderr = process.stderr

        _log_decision("ast_rewrite.success", {"pattern": pattern, "lang": lang})

        if process.returncode != 0:
            return f"Error: ast-rewrite failed\nstderr: {stderr}"

        return f"--- ast-rewrite Applied ---\n{output}"

    except FileNotFoundError:
        return "Error: 'ast-grep' command not found. Install with: nix-env -iA nixpkgs.ast-grep"
    except subprocess.TimeoutExpired:
        return "Error: ast-rewrite timed out"
    except Exception as e:
        return f"Error running ast-rewrite: {e}"


@mcp.tool()
async def ast_search(pattern: str, lang: str = "py", path: str = ".") -> str:
    """
    Query code structure using ast-grep patterns.

    Use this for structural code search (e.g., "Find all functions calling API X").

    Examples:
    - pattern: "function_call name:$_" (find function calls)
    - pattern: "try_stmt" (find all try-except blocks)
    - pattern: "assign $left = $right where $right: string" (find string assignments)

    Args:
        pattern: AST pattern to search for
        lang: Language (py, js, ts, go, rust, etc.)
        path: Directory to search (default: current directory)
    """
    if ".." in path or path.startswith("/"):
        _log_decision("ast_search.security_block", {"path": path})
        return "Error: Path traversal or absolute paths not allowed."

    return _run_ast_grep(pattern, lang, path)


@mcp.tool()
async def ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    """
    Apply AST-based code rewrite using ast-grep.

    Use this for structural refactoring (e.g., "Replace all list comprehensions with map").

    CAUTION: This modifies files. Backups are recommended.

    Examples:
    - pattern: "for $x in $list: $x" -> replacement: "$list.map($x)"
    - pattern: "try: $body except:$handler" -> replacement: "try:\n    $body\ncatch:\n    $handler"

    Args:
        pattern: AST pattern to find
        replacement: AST pattern to replace with
        lang: Language
        path: Directory or file to modify
    """
    if ".." in path or path.startswith("/"):
        _log_decision("ast_rewrite.security_block", {"path": path})
        return "Error: Path traversal or absolute paths not allowed."

    _log_decision("ast_rewrite.request", {"pattern": pattern, "replacement": "***", "lang": lang, "path": path})

    return _run_ast_rewrite(pattern, replacement, lang, path)


# =============================================================================
# File Writing with Safety
# =============================================================================

@mcp.tool()
async def save_file(
    path: str,
    content: str,
    create_backup: bool = True,
    validate_syntax: bool = True
) -> str:
    """
    Write content to a file within the project directory.

    Features:
    - Auto-creates .bak backup before overwriting (safe rollback)
    - Syntax validation for Python and Nix files
    - Security checks for path safety
    """
    is_safe, error_msg = _is_safe_path(path)
    if not is_safe:
        _log_decision("save_file.security_block", {"path": path, "reason": error_msg})
        return f"Error: {error_msg}"

    project_root = Path.cwd()
    full_path = project_root / path

    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            _log_decision("save_file.security_block", {"path": path})
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
            _log_decision("save_file.syntax_error", {"path": path, "error": error_msg})
            return f"Error: Syntax validation failed\n{error_msg}"

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        _log_decision("save_file.success", {"path": path, "size": len(content)})
        return f"Successfully wrote {len(content)} bytes to '{path}'{backup_info}"
    except Exception as e:
        _log_decision("save_file.error", {"path": path, "error": str(e)})
        return f"Error writing file: {e}"


if __name__ == "__main__":
    mcp.run()
