"""
structural_editing/scripts/structural.py - Structural Editing Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import re
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
    logger.warning("omni_core_rs not found. StructuralEditing will use fallback.")


def _fallback_replace(content: str, pattern: str, replacement: str) -> str:
    """Fallback implementation using simple string replace.

    This is less precise than AST-based matching but provides basic functionality.
    """
    # Extract simple identifier from pattern (ignore $VAR captures)
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


@skill_script(
    name="structural_replace",
    category="write",
    description="Perform structural replace on content using AST patterns.",
)
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


@skill_script(
    name="structural_preview",
    category="read",
    description="Preview structural replace on a file without modifying it.",
)
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


@skill_script(
    name="structural_apply",
    category="write",
    description="Apply structural replace to a file (MODIFIES THE FILE).",
)
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


@skill_script(
    name="refactor_repository",
    category="write",
    description="MASS REFACTORING TOOL. Change code patterns across the ENTIRE repository.",
)
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
    using Rust's rayon thread pool.
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


@skill_script(
    name="get_edit_info",
    category="read",
    description="Get information about the structural editing capability.",
)
def get_edit_info() -> dict[str, Any]:
    """
    Get information about the structural editing capability.
    """
    return {
        "name": "structural_editing",
        "version": "1.1.0",
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
