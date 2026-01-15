"""
code_navigation/scripts/navigation.py - Code Navigation Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

from pathlib import Path
from typing import Any

import structlog

from agent.skills.decorators import skill_script

logger = structlog.get_logger(__name__)

# Check if Rust bindings are available
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("omni_core_rs not found. CodeNavigation will use fallback.")


@skill_script(
    name="outline_file",
    category="read",
    description="Generate a high-level outline (skeleton) of a source file.",
)
def outline_file(path: str, language: str | None = None) -> str:
    """
    Generate a high-level outline (skeleton) of a source file.

    Reduces context usage by providing symbolic representation instead of full content.
    AX Philosophy: "Map over Territory" - understand structure before diving into details.
    """
    if not RUST_AVAILABLE:
        # Fallback: simple file read (not efficient but functional)
        try:
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


@skill_script(
    name="count_symbols",
    category="read",
    description="Count the number of symbols (classes, functions, etc.) in a file.",
)
def count_symbols(path: str, language: str | None = None) -> dict[str, Any]:
    """
    Count the number of symbols (classes, functions, etc.) in a file.

    Useful for quickly assessing file complexity before reading.
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


@skill_script(
    name="search_code",
    category="read",
    description="Search for AST patterns in a single file using ast-grep syntax.",
)
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    """
    Search for AST patterns in a single file using ast-grep syntax.

    Unlike text search (grep), this searches for CODE PATTERNS, not strings.
    Perfect for finding specific code constructs like function calls, class definitions, etc.
    """
    if not RUST_AVAILABLE:
        # Fallback: simple grep (less precise but available)
        try:
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


@skill_script(
    name="search_directory",
    category="read",
    description="Search for AST patterns recursively in a directory.",
)
def search_directory(path: str, pattern: str, file_pattern: str | None = None) -> str:
    """
    Search for AST patterns recursively in a directory.

    Unlike naive grep, this uses AST patterns for precise, semantic matching.
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
