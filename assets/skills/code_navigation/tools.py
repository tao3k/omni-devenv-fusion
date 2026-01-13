"""
agent/skills/code_navigation/tools.py
Phase 50: The Cartographer - Code Navigation Skill
Phase 51: The Hunter - Structural Code Search

Provides structural awareness using AST-based parsing.
AX Philosophy: "Map over Territory" - reduce context by providing outlines.

Features:
- outline_file: Generate symbolic outline for any source file
- search_code: Search for AST patterns in a single file
- search_directory: Search for AST patterns recursively
- AST-based extraction using ast-grep-core 0.40.5
- Support for Python, Rust, JavaScript, TypeScript

Part of Phase 50.5: The Map Room & Phase 51: The Hunter
"""

import structlog
from typing import Any

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# Check if Rust bindings are available
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("omni_core_rs not found. CodeNavigation will use fallback.")


@skill_command("outline_file")
def outline_file(path: str, language: str | None = None) -> str:
    """
    Generate a high-level outline (skeleton) of a source file.

    Reduces context usage by providing symbolic representation instead of full content.
    AX Philosophy: "Map over Territory" - understand structure before diving into details.

    Args:
        path: Path to the source file (relative or absolute)
        language: Optional language hint (python, rust, javascript, typescript)

    Returns:
        Formatted outline showing classes, functions, structs, etc.
        Returns error message if outline cannot be generated.

    Example:
        // OUTLINE: src/agent/core/base.py
        // Total symbols: 12
        L1    [class]     AgentBase ...
        L15   [function]  create_agent ...
        L42   [method]    initialize ...
    """
    if not RUST_AVAILABLE:
        # Fallback: simple file read (not efficient but functional)
        try:
            from pathlib import Path

            content = Path(path).read_text()
            lines = content.split("\n")
            outline = []
            outline.append(f"// OUTLINE: {path}")
            outline.append(f"// Total lines: {len(lines)}")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("class ") or stripped.startswith("def "):
                    outline.append(f"L{i} {stripped}")
            if not outline:
                return f"// 🗺️ OUTLINE: {path}\n[No structural symbols found.]"
            return "\n".join(outline)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    try:
        outline = omni_core_rs.get_file_outline(path, language)
        if not outline or outline.strip() == "":
            return f"// 🗺️ OUTLINE: {path}\n[No structural symbols found.]"
        return outline
    except Exception as e:
        logger.error("Failed to outline file", path=path, error=str(e))
        return f"Error generating outline: {str(e)}"


@skill_command("count_symbols")
def count_symbols(path: str, language: str | None = None) -> dict[str, Any]:
    """
    Count the number of symbols (classes, functions, etc.) in a file.

    Useful for quickly assessing file complexity before reading.

    Returns:
        Dictionary with symbol counts by kind and total.
    """
    if not RUST_AVAILABLE:
        return {"error": "omni_core_rs not available"}

    try:
        outline = omni_core_rs.get_file_outline(path, language)
        if "No symbols found" in outline:
            return {"total": 0, "by_kind": {}}

        # Parse outline to count symbols
        lines = outline.split("\n")
        counts: dict[str, int] = {}
        for line in lines[2:]:  # Skip header lines
            if line.strip():
                # Extract kind from [class], [function], etc.
                start = line.find("[")
                end = line.find("]")
                if start != -1 and end != -1:
                    kind = line[start + 1 : end].lower()
                    counts[kind] = counts.get(kind, 0) + 1

        return {"total": sum(counts.values()), "by_kind": counts}
    except Exception as e:
        logger.error("Failed to count symbols", path=path, error=str(e))
        return {"error": str(e)}


# ============================================================================
# Phase 51: The Hunter - Structural Code Search
# ============================================================================


@skill_command("search_code")
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    """
    Search for AST patterns in a single file using ast-grep syntax.

    Unlike text search (grep), this searches for CODE PATTERNS, not strings.
    Perfect for finding specific code constructs like function calls, class definitions, etc.

    AX Philosophy: "Surgical precision" - find exactly what you mean, not fuzzy matches.

    Args:
        path: Path to the source file
        pattern: ast-grep pattern (e.g., "connect($ARGS)", "class $NAME")
        language: Optional language hint (python, rust, javascript, typescript)

    Returns:
        Formatted search results showing match locations and captured variables.

    Examples:
        # Find all function calls to 'connect'
        search_code("src/", "connect($ARGS)")

        # Find all class definitions
        search_code("src/", "class $NAME")

        # Find all method definitions
        search_code("src/", "def $NAME($PARAMS)")

    Pattern Syntax:
        - $NAME: Capture any identifier
        - $ARGS: Capture any argument list
        - $PARAMS: Capture any parameter list
        - $EXPR: Capture any expression
    """
    if not RUST_AVAILABLE:
        # Fallback: simple grep (less precise but available)

        try:
            from pathlib import Path

            content = Path(path).read_text()
            lines = content.split("\n")
            results = [f"// SEARCH: {path}", f"// Pattern: {pattern} (fallback: text search)"]
            for i, line in enumerate(lines, 1):
                if pattern.lower() in line.lower():
                    results.append(f"L{i}: {line.strip()}")
            if len(results) == 2:
                return f"[No matches for pattern in {path}]"
            return "\n".join(results)
        except Exception as e:
            return f"Error searching file: {str(e)}"

    try:
        result = omni_core_rs.search_code(path, pattern, language)
        return result
    except Exception as e:
        logger.error("Failed to search file", path=path, pattern=pattern, error=str(e))
        return f"Error searching: {str(e)}"


@skill_command("search_directory")
def search_directory(path: str, pattern: str, file_pattern: str | None = None) -> str:
    """
    Search for AST patterns recursively in a directory.

    Unlike naive grep, this uses AST patterns for precise, semantic matching.

    AX Philosophy: "Hunt with precision" - find code constructs across the codebase.

    Args:
        path: Directory to search in
        pattern: ast-grep pattern (e.g., "connect($ARGS)", "class $NAME")
        file_pattern: Optional glob pattern (e.g., "**/*.py", "**/*.rs")

    Returns:
        Formatted search results across all matching files.

    Examples:
        # Find all 'connect' calls in Python files
        search_directory("src/", "connect($ARGS)", "**/*.py")

        # Find all class definitions
        search_directory("lib/", "class $NAME")

        # Find all async function definitions
        search_directory(".", "async def $NAME($PARAMS)")

    Pattern Syntax:
        - $NAME: Capture any identifier
        - $ARGS: Capture any argument list
        - $EXPR: Capture any expression
    """
    if not RUST_AVAILABLE:
        return "Error: Rust bindings (omni_core_rs) not available. Run 'just build-rust' first."

    try:
        result = omni_core_rs.search_directory(path, pattern, file_pattern)
        return result
    except Exception as e:
        logger.error(
            "Failed to search directory",
            path=path,
            pattern=pattern,
            error=str(e),
        )
        return f"Error searching directory: {str(e)}"
