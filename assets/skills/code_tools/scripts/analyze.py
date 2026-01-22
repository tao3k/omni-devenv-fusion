"""
Code Analysis Skill (Refactored - Lean & Secured)

Philosophy:
- Zero Config: Assumes tools (grep) are in System PATH.
- Security: Operations strictly constrained to ConfigPaths.project_root.
- Focus: Parsing and structuring data for the LLM.

Commands:
- search_code: Text search using system grep
- list_project_structure: Directory tree view
"""

from pathlib import Path
from typing import Any
import subprocess
import shutil
import os

# Modern Foundation API
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.code_tools.analyze")

# Try to import Rust-powered AST (Structural Code Intelligence)
try:
    from omni_core_rs import search_code as rust_search_code
    from omni_core_rs import search_directory as rust_search_directory

    _RUST_AST_AVAILABLE = True
except ImportError:
    _RUST_AST_AVAILABLE = False
    logger.debug("Rust AST engine not available, falling back to Python/grep")


# =============================================================================
# Grep-Based Search (System Tool, No Config)
# =============================================================================


@skill_command(
    name="search_code",
    description="Search for code patterns using system grep (recursive).",
    autowire=True,
)
def search_code(
    pattern: str,
    include: str | None = None,
    exclude: str | None = None,
    case_sensitive: bool = True,
    max_results: int = 100,
    # Injected (No Settings needed!)
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Search code base safely.
    Relies on system 'grep' being available in PATH.
    """
    if paths is None:
        paths = ConfigPaths()

    try:
        root = paths.project_root

        # 1. Auto-Discovery (Environment is Truth)
        grep_cmd = shutil.which("grep")
        if not grep_cmd:
            return {"success": False, "error": "System tool 'grep' not found in PATH."}

        # 2. Build Command
        # -r: recursive, -n: line number, -I: ignore binary
        cmd = [grep_cmd, "-r", "-n", "-I"]

        if not case_sensitive:
            cmd.append("-i")

        # Standard Excludes (Hardcoded best practices, no config bloat)
        default_excludes = [
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            ".mypy_cache",
            "target",
            "dist",
        ]
        for d in default_excludes:
            cmd.extend(["--exclude-dir", d])

        if exclude:
            cmd.extend(["--exclude", exclude])
        if include:
            cmd.extend(["--include", include])

        cmd.append(pattern)
        cmd.append(".")  # Search from current cwd (which we set to root)

        # 3. Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=root,  # SECURITY: Enforce root as working directory
            check=False,
        )

        if result.returncode > 1:
            return {"success": False, "error": f"Grep failed: {result.stderr}"}

        # 4. Parse & Limit (Logic Layer)
        matches = []
        lines = result.stdout.splitlines()
        truncated = False

        if len(lines) > max_results:
            lines = lines[:max_results]
            truncated = True

        for line in lines:
            try:
                # grep output format: file:line:content
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append(
                        {
                            "file": parts[0],
                            "line": int(parts[1]),
                            "content": parts[2].strip(),
                        }
                    )
            except ValueError:
                continue

        return {
            "success": True,
            "count": len(matches),
            "total_found": len(result.stdout.splitlines()),
            "truncated": truncated,
            "matches": matches,
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Project Structure (Pure Python, No External Dependencies)
# =============================================================================


@skill_command(
    name="list_project_structure",
    description="Get a high-level view of the project structure.",
    autowire=True,
)
def list_project_structure(
    depth: int = 2,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Generates a directory tree safely."""
    if paths is None:
        paths = ConfigPaths()

    try:
        root = paths.project_root
        structure = []

        start_depth = str(root).count(os.sep)

        # Pure Python implementation - no external dependencies
        for dirpath, dirnames, filenames in os.walk(root):
            # Filter hidden/system dirs in place
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d not in ["__pycache__", "node_modules"]
            ]

            curr_depth = dirpath.count(os.sep) - start_depth
            if curr_depth >= depth:
                dirnames[:] = []

            rel_path = os.path.relpath(dirpath, root)
            if rel_path == ".":
                rel_path = ""

            structure.append(
                {
                    "path": rel_path,
                    "dirs": dirnames.copy(),
                    "files": [f for f in filenames if not f.startswith(".")],
                }
            )

        return {"success": True, "root": str(root), "structure": structure}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Rust-Powered AST Search (Advanced Feature)
# =============================================================================


@skill_command(
    name="ast_search",
    description="Structural code search using Rust-powered AST (ast-grep).",
    autowire=True,
)
async def ast_search(
    file_path: str,
    pattern: str,
    language: str | None = None,
    paths: ConfigPaths | None = None,
) -> str:
    """Search file using Rust AST engine."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target = (root / file_path).resolve()

    if not str(target).startswith(str(root)):
        return "Error: Access denied to paths outside project root."

    if not target.exists():
        return f"Error: File not found: {file_path}"

    if not _RUST_AST_AVAILABLE:
        return "Error: Rust AST engine not available. Install omni-core-rs."

    try:
        result = rust_search_code(str(target), pattern, language)
        return result if result else f"No matches found for pattern: {pattern}"
    except Exception as e:
        return f"Search error: {e}"


@skill_command(
    name="ast_search_dir",
    description="Recursive structural search in a directory using Rust AST engine.",
    autowire=True,
)
async def ast_search_dir(
    path: str,
    pattern: str,
    file_pattern: str | None = None,
    paths: ConfigPaths | None = None,
) -> str:
    """Search directory using Rust AST engine."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target = (root / path).resolve()

    if not str(target).startswith(str(root)):
        return "Error: Access denied to paths outside project root."

    if not target.exists():
        return f"Error: Directory not found: {path}"

    if not _RUST_AST_AVAILABLE:
        return "Error: Rust AST engine not available. Install omni-core-rs."

    try:
        result = rust_search_directory(str(target), pattern, file_pattern)
        return result if result else f"No matches found for pattern: {pattern}"
    except Exception as e:
        return f"Search error: {e}"


__all__ = ["search_code", "list_project_structure", "ast_search", "ast_search_dir"]
