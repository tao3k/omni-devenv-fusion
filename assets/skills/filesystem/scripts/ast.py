"""
filesystem/scripts/ast.py - AST-based Code Operations

Phase 63: Migrated from tools.py to scripts pattern.
"""

from pathlib import Path

from common.mcp_core import is_safe_path, normalize_path, run_subprocess
from agent.skills.decorators import skill_script


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


def _convert_path_to_relative(path: str) -> str:
    """Convert absolute path to relative path if within project."""
    is_safe, error_msg, normalized = normalize_path(path)
    if not is_safe:
        raise ValueError(error_msg)
    return normalized


@skill_script(
    name="ast_search",
    category="read",
    description="Query code structure using ast-grep patterns.",
    inject_root=True,
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

    Supports absolute paths - they will be converted to relative paths automatically.
    """
    try:
        path = _convert_path_to_relative(path)
    except ValueError as e:
        return f"Error: {e}"

    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_grep(pattern, lang, path)


@skill_script(
    name="ast_rewrite",
    category="write",
    description="Apply AST-based code rewrite using ast-grep.",
    inject_root=True,
)
async def ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    """
    Apply AST-based code rewrite using ast-grep.

    Rewrite Examples:
    - pattern: "print($MSG)" -> replacement: "logger.info($MSG)"
    - pattern: "def $NAME($ARGS):" -> replacement: "async def $NAME($ARGS):"

    Supports absolute paths - they will be converted to relative paths automatically.
    """
    try:
        path = _convert_path_to_relative(path)
    except ValueError as e:
        return f"Error: {e}"

    is_safe, error_msg = is_safe_path(path)
    if not is_safe:
        return f"Error: {error_msg}"

    return await _run_ast_rewrite(pattern, replacement, lang, path)
