"""
code_tools/scripts/refactor.py - Structural Editing Commands

Phase 68: Migrated from structural_editing.
AST-based code refactoring with preview-before-apply workflow.
"""

import re
from pathlib import Path
from typing import Any

import structlog

from agent.skills.decorators import skill_script

logger = structlog.get_logger(__name__)

try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("omni_core_rs not found. StructuralEditing will use fallback.")


def _fallback_replace(content: str, pattern: str, replacement: str) -> str:
    """Fallback implementation using simple string replace.

    This is less precise than AST-based matching but provides basic functionality.
    """
    literal_pattern = re.sub(r"\$\w+", ".*?", pattern)

    try:
        matches = list(re.finditer(literal_pattern, content))
        if not matches:
            return "[No matches found (fallback mode)]\n"

        output = [
            "// STRUCTURAL REPLACE (fallback mode - Rust bindings not available)",
            f"// Pattern: {pattern}",
            f"// Replacement: {replacement}",
            f"// Matches: {len(matches)}",
            "",
            "Fallback mode provides limited functionality.",
            "   Run 'just build-rust' to enable full AST-based matching.",
        ]
        return "\n".join(output)
    except re.error as e:
        return f"[Regex error in fallback mode: {e}]"


@skill_script(
    name="structural_replace",
    category="write",
    description="""
    Performs structural replace on content using AST patterns.

    Unlike regex replace, this understands code structure:
    - Pattern `connect($ARGS)` matches function calls, not strings containing "connect"
    - Variables like `$ARGS` capture actual code constructs

    AX Philosophy: "The Surgeon operates with precision, not force."

    Args:
        pattern: ast-grep pattern to match (e.g., `connect($ARGS)`).
        replacement: Replacement pattern (e.g., `async_connect($ARGS)`).
        language: Programming language (`python`, `rust`, `javascript`, `typescript`).
        content: Source code content to modify (optional if path provided).
        path: Path to file to modify (optional if content provided).

    Returns:
        Formatted string showing diff and edit locations.

    Example:
        @omni("code_tools.structural_replace", {"pattern": "connect($ARGS)", "replacement": "async_connect($ARGS)", "language": "python"})
    """,
)
def structural_replace(
    pattern: str,
    replacement: str,
    language: str,
    content: str | None = None,
    path: str | None = None,
) -> str:
    if path and not content:
        from pathlib import Path as PathLib

        file_path = PathLib(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        content = file_path.read_text()

    if not content:
        return "Error: Either content or path must be provided"

    if not RUST_AVAILABLE:
        return _fallback_replace(content, pattern, replacement)

    try:
        return omni_core_rs.structural_replace(content, pattern, replacement, language)
    except Exception as e:
        logger.error(
            "Structural replace failed",
            pattern=pattern,
            replacement=replacement,
            error=str(e),
        )
        return f"Error in structural replace: {str(e)}"


@skill_script(
    name="structural_preview",
    category="read",
    description="""
    Previews structural replace on a file without modifying it.

    Always use this before structural_apply to verify changes are correct.

    AX Philosophy: "Preview twice, apply once."

    Args:
        path: Path to the file to preview changes on.
        pattern: ast-grep pattern to match.
        replacement: Replacement pattern.
        language: Programming language (optional, auto-detected if not provided).

    Returns:
        Preview output showing what would be changed, or error message.

    Example:
        @omni("code_tools.structural_preview", {"path": "src/main.py", "pattern": "print($MSG)", "replacement": "logger.info($MSG)"})
    """,
)
def structural_preview(
    path: str,
    pattern: str,
    replacement: str,
    language: str | None = None,
) -> str:
    if not RUST_AVAILABLE:
        return "Error: Rust bindings (omni_core_rs) not available. Run 'just build-rust' first."

    try:
        return omni_core_rs.structural_preview(path, pattern, replacement, language)
    except Exception as e:
        logger.error(
            "Structural preview failed",
            path=path,
            pattern=pattern,
            error=str(e),
        )
        return f"Error in structural preview: {str(e)}"


@skill_script(
    name="structural_apply",
    category="write",
    description="""
    Applies structural replace to a file (MODIFIES THE FILE).

    CAUTION: This modifies the file in place. Always use structural_preview first.

    AX Philosophy: "The Surgeon cuts only where necessary."

    Args:
        path: Path to the file to modify.
        pattern: ast-grep pattern to match.
        replacement: Replacement pattern.
        language: Programming language (optional, auto-detected if not provided).

    Returns:
        Confirmation message with change details, or error message.

    Example:
        @omni("code_tools.structural_apply", {"path": "src/main.py", "pattern": "print($MSG)", "replacement": "logger.info($MSG)"})
    """,
)
def structural_apply(
    path: str,
    pattern: str,
    replacement: str,
    language: str | None = None,
) -> str:
    if not RUST_AVAILABLE:
        return "Error: Rust bindings (omni_core_rs) not available. Run 'just build-rust' first."

    try:
        return omni_core_rs.structural_apply(path, pattern, replacement, language)
    except Exception as e:
        logger.error(
            "Structural apply failed",
            path=path,
            pattern=pattern,
            error=str(e),
        )
        return f"Error in structural apply: {str(e)}"


@skill_script(
    name="refactor_repository",
    category="write",
    description="""
    MASS REFACTORING TOOL. Changes code patterns across the ENTIRE repository.

    This is the "nuclear option" - processes thousands of files in parallel
    using Rust's rayon thread pool.

    Args:
        search_pattern: Pattern to search for (ast-grep syntax).
        rewrite_pattern: Replacement pattern.
        path: Root directory to search. Defaults to current directory (`.`).
        file_pattern: File glob pattern. Defaults to `**/*.py`.
        dry_run: If `true`, only show what would be changed. Defaults to `true`.

    Returns:
        Report with files scanned, changed, replacements count, and errors.

    Example:
        @omni("code_tools.refactor_repository", {"search_pattern": "print($MSG)", "rewrite_pattern": "logger.info($MSG)", "dry_run": false})
    """,
)
def refactor_repository(
    search_pattern: str,
    rewrite_pattern: str,
    path: str = ".",
    file_pattern: str = "**/*.py",
    dry_run: bool = True,
) -> str:
    if not RUST_AVAILABLE:
        return (
            "Error: Rust bindings (omni_core_rs) not available.\n"
            "This feature requires Phase 58's heavy-duty batch refactoring.\n"
            "Run 'just build-rust' to enable."
        )

    root_path = Path(path)
    if not root_path.exists():
        return f"Error: Path does not exist: {path}"
    if not root_path.is_dir():
        return f"Error: Path is not a directory: {path}"

    try:
        stats = omni_core_rs.batch_structural_replace(
            str(root_path.resolve()),
            search_pattern,
            rewrite_pattern,
            file_pattern,
            dry_run,
        )

        status_emoji = "DRY RUN" if dry_run else "APPLIED"
        status_text = "DRY RUN" if dry_run else "APPLIED"

        report_lines = [
            f"Batch Refactor Report [{status_text}]",
            "=" * 50,
            f"Root Path: {root_path}",
            f"Pattern: `{search_pattern}` -> `{rewrite_pattern}`",
            f"File Pattern: {file_pattern}",
            "-" * 50,
            f"Files Scanned: {stats.files_scanned}",
            f"Files Changed: {stats.files_changed}",
            f"Replacements: {stats.replacements}",
        ]

        if stats.files_changed > 0:
            if dry_run:
                report_lines.append("Tip: Set dry_run=False to apply changes.")
            else:
                report_lines.append("All changes applied successfully!")
        else:
            report_lines.append("No matches found for the given pattern.")

        if stats.errors:
            report_lines.append(f"\nErrors ({len(stats.errors)}):")
            for err in stats.errors[:5]:
                report_lines.append(f"  - {err}")
            if len(stats.errors) > 5:
                report_lines.append(f"  ... and {len(stats.errors) - 5} more")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(
            "Batch refactor failed",
            path=path,
            pattern=search_pattern,
            error=str(e),
        )
        return f"Critical Batch Error: {str(e)}"


@skill_script(
    name="get_edit_info",
    category="read",
    description="""
    Gets information about the structural editing capability.

    Returns:
        Dict with name, version, rust_available status, supported languages,
        features list, phase info, and performance characteristics.
    """,
)
def get_edit_info() -> dict[str, Any]:
    return {
        "name": "code_tools",
        "version": "1.0.0",
        "rust_available": RUST_AVAILABLE,
        "supported_languages": ["python", "rust", "javascript", "typescript"],
        "features": [
            "AST-based pattern matching",
            "Variable capture ($ARGS, $NAME, etc.)",
            "Unified diff generation",
            "Preview before apply workflow",
            "Phase 58: Heavy-duty batch refactoring (rayon parallel)",
        ],
        "phase": "Phase 68: Code Tools Merge",
        "performance": {
            "batch_mode": "10,000 files = 1 FFI call",
            "parallelism": "Uses all CPU cores",
            "speedup": "~100x vs Python loop",
        },
    }
