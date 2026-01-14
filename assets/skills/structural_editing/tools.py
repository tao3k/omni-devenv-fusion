"""
agent/skills/structural_editing/tools.py
Phase 52: The Surgeon - Structural Code Refactoring
Phase 58: The Ouroboros - Heavy-Duty Batch Refactoring

Provides AST-based code modification using ast-grep patterns.
AX Philosophy: "Surgical precision" - modify exactly what you mean, not fuzzy matches.

Features:
- structural_replace: Replace patterns in content strings
- structural_preview: Preview changes on files (no modification)
- structural_apply: Apply changes to files (modifies files)
- refactor_repository: MASS REFACTORING across entire codebase (Phase 58)
- Diff generation showing exact changes
- Multi-language support (Python, Rust, JavaScript, TypeScript)

Part of Phase 52: The Surgeon (CCA-Aligned Code Modification)
Phase 58: The Ouroboros (Self-Eating Snake)
"""

import structlog
from pathlib import Path
from typing import Any

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# Check if Rust bindings are available
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("omni_core_rs not found. StructuralEditing will use fallback.")


@skill_command("structural_replace")
def structural_replace(
    content: str,
    pattern: str,
    replacement: str,
    language: str,
) -> str:
    """
    Perform structural replace on content using AST patterns.

    Unlike regex replace, this understands code structure:
    - Pattern "connect($ARGS)" matches function calls, not strings containing "connect"
    - Variables like $ARGS capture actual code constructs

    AX Philosophy: "The Surgeon operates with precision, not force."

    Args:
        content: Source code content to modify
        pattern: ast-grep pattern to match (e.g., "connect($ARGS)")
        replacement: Replacement pattern (e.g., "async_connect($ARGS)")
        language: Programming language (python, rust, javascript, typescript)

    Returns:
        Formatted string showing diff and edit locations.

    Example:
        structural_replace(
            content="x = old_api(data)",
            pattern="old_api($$$)",  # Use $$$ for variadic args
            replacement="new_api($$$)",
            language="python"
        )
        # Returns diff showing: "x = new_api(data)"
    """
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


@skill_command("structural_preview")
def structural_preview(
    path: str,
    pattern: str,
    replacement: str,
    language: str | None = None,
) -> str:
    """
    Preview structural replace on a file without modifying it.

    Always use this before structural_apply to verify changes are correct.

    AX Philosophy: "Preview twice, apply once."

    Args:
        path: Path to the source file
        pattern: ast-grep pattern to match
        replacement: Replacement pattern
        language: Optional language hint (auto-detected if None)

    Returns:
        Formatted string showing what changes would be made.

    Example:
        structural_preview(
            path="src/client.py",
            pattern="old_connect($$$)",  # Use $$$ for variadic args
            replacement="new_connect($$$)"
        )
        # Shows diff without modifying the file
    """
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


@skill_command("structural_apply")
def structural_apply(
    path: str,
    pattern: str,
    replacement: str,
    language: str | None = None,
) -> str:
    """
    Apply structural replace to a file (MODIFIES THE FILE).

    **CAUTION**: This modifies the file in place. Always use structural_preview first.

    AX Philosophy: "The Surgeon cuts only where necessary."

    Args:
        path: Path to the source file
        pattern: ast-grep pattern to match
        replacement: Replacement pattern
        language: Optional language hint (auto-detected if None)

    Returns:
        Formatted string showing applied changes.

    Example:
        # First preview (use $$$ for variadic args)
        structural_preview("src/client.py", "old_api($$$)", "new_api($$$)")

        # Then apply after confirming
        structural_apply("src/client.py", "old_api($$$)", "new_api($$$)")
    """
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


# ============================================================================
# Phase 58: The Ouroboros - Heavy-Duty Batch Refactoring
# ============================================================================


@skill_command("refactor_repository")
def refactor_repository(
    search_pattern: str,
    rewrite_pattern: str,
    path: str = ".",
    file_pattern: str = "**/*.py",
    dry_run: bool = True,
) -> str:
    """
    MASS REFACTORING TOOL. Change code patterns across the ENTIRE repository.

    This is the "nuclear option" - it processes thousands of files in parallel
    using Rust's rayon thread pool. Perfect for:
    - Renaming functions across all files
    - Changing API calls throughout codebase
    - Modernizing legacy patterns (print -> logger)
    - Adding type hints or decorators everywhere

    AX Philosophy: "Move the loop to Rust. Stop crossing the border for small tasks."

    Args:
        search_pattern: ast-grep pattern to find (e.g., 'print($A)' or 'old_func($ARGS)')
        rewrite_pattern: Replacement pattern (e.g., 'logger.info($A)' or 'new_func($ARGS)')
        path: Root directory to start search (default: current directory)
        file_pattern: Glob pattern for files to include (default: **/*.py)
        dry_run: If True, only list what would change. Set False to apply changes.

    Returns:
        A summary report of files scanned, changed, and any errors.

    Example:
        # Dry run first
        refactor_repository(
            search_pattern="print($A)",
            rewrite_pattern="logger.info($A)",
            path="packages/python",
            dry_run=True
        )

        # Then apply
        refactor_repository(
            search_pattern="print($A)",
            rewrite_pattern="logger.info($A)",
            path="packages/python",
            dry_run=False
        )

    Performance:
        - 10,000 files = 1 FFI call (not 10,000!)
        - Uses all CPU cores via rayon
        - ~100x faster than Python loop
    """
    if not RUST_AVAILABLE:
        return (
            "Error: Rust bindings (omni_core_rs) not available.\n"
            "This feature requires Phase 58's heavy-duty batch refactoring.\n"
            "Run 'just build-rust' to enable."
        )

    # Validate path
    root_path = Path(path)
    if not root_path.exists():
        return f"Error: Path does not exist: {path}"
    if not root_path.is_dir():
        return f"Error: Path is not a directory: {path}"

    try:
        # Call the Phase 58 heavy equipment
        stats = omni_core_rs.batch_structural_replace(
            str(root_path.resolve()),
            search_pattern,
            rewrite_pattern,
            file_pattern,
            dry_run,
        )

        # Generate AX-friendly report
        status_emoji = "🔍" if dry_run else "⚡"
        status_text = "DRY RUN" if dry_run else "APPLIED"

        report_lines = [
            f"{status_emoji} Batch Refactor Report [{status_text}]",
            "=" * 50,
            f"📂 Root Path: {root_path}",
            f"🎯 Pattern: `{search_pattern}` → `{rewrite_pattern}`",
            f"📄 File Pattern: {file_pattern}",
            "-" * 50,
            f"📊 Files Scanned: {stats.files_scanned}",
            f"✏️  Files Changed: {stats.files_changed}",
            f"🔢 Replacements: {stats.replacements}",
        ]

        if stats.files_changed > 0:
            if dry_run:
                report_lines.append("💡 Tip: Set dry_run=False to apply changes.")
            else:
                report_lines.append("✅ All changes applied successfully!")
        else:
            report_lines.append("ℹ️  No matches found for the given pattern.")

        if stats.errors:
            report_lines.append(f"\n⚠️  Errors ({len(stats.errors)}):")
            for err in stats.errors[:5]:  # Limit to 5 to avoid spam
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
        return f"❌ Critical Batch Error: {str(e)}"


def _fallback_replace(content: str, pattern: str, replacement: str) -> str:
    """Fallback implementation using simple string replace.

    This is less precise than AST-based matching but provides basic functionality.
    """
    # Extract simple identifier from pattern (ignore $VAR captures)
    import re

    # Very basic: extract literal parts of pattern
    # This won't handle $ARGS properly but provides minimal functionality
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
            "⚠️  Fallback mode provides limited functionality.",
            "   Run 'just build-rust' to enable full AST-based matching.",
        ]
        return "\n".join(output)
    except re.error as e:
        return f"[Regex error in fallback mode: {e}]"


@skill_command("get_edit_info")
def get_edit_info() -> dict[str, Any]:
    """
    Get information about the structural editing capability.

    Returns:
        Dictionary with capability information.
    """
    return {
        "name": "structural_editing",
        "version": "1.1.0",  # Phase 58 update
        "rust_available": RUST_AVAILABLE,
        "supported_languages": ["python", "rust", "javascript", "typescript"],
        "features": [
            "AST-based pattern matching",
            "Variable capture ($ARGS, $NAME, etc.)",
            "Unified diff generation",
            "Preview before apply workflow",
            "Phase 58: Heavy-duty batch refactoring (rayon parallel)",
        ],
        "phase": "Phase 58: The Ouroboros (Self-Eating Snake)",
        "performance": {
            "batch_mode": "10,000 files = 1 FFI call",
            "parallelism": "Uses all CPU cores",
            "speedup": "~100x vs Python loop",
        },
    }
