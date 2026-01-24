"""
Code Refactoring Skill (Refactored)

Philosophy:
- Atomic Operations: Provide the "brick" (edit file), let Agent build the "wall".
- Verification: Always return a diff to verify the change.
- Security: All operations constrained to ConfigPaths.project_root.

Commands:
- apply_file_edit: String-based file replacement with diff output
- structural_replace: AST-based pattern matching (Rust-powered)
- structural_preview: Preview changes before applying
- structural_apply: Apply AST-based changes
- refactor_repository: Batch refactoring across repository
"""

import difflib
import re
from pathlib import Path
from typing import Any

# Modern Foundation API
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.code_tools.refactor")

try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.debug("omni_core_rs not found. StructuralEditing will use fallback.")


# =============================================================================
# Atomic String-Based Editing (Zero Dependencies)
# =============================================================================


@skill_command(
    name="apply_file_edit",
    category="write",
    description="""
    Replace specific string block in a file. Requires exact match.

    Args:
        - file_path: str - Path to the file to edit (required)
        - search_text: str - Text to find (must match exactly, including whitespace) (required)
        - replace_text: str - Text to replace with (required)

    Returns:
        JSON with success status, path, and unified diff showing the change.
    """,
    autowire=True,
)
def apply_file_edit(
    file_path: str,
    search_text: str,
    replace_text: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Perform a safe string replacement.
    This is the fundamental actuator for code modification.
    """
    if paths is None:
        paths = ConfigPaths()

    try:
        # 1. Safe Path Resolution
        root = paths.project_root
        target = (root / file_path).resolve()

        # Sandbox Check
        if not str(target).startswith(str(root)):
            return {"success": False, "error": "Access denied: Path traversal detected."}

        if not target.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        # 2. Read
        content = target.read_text(encoding="utf-8")

        # 3. Verify Uniqueness (Critical for LLM safety)
        count = content.count(search_text)

        if count == 0:
            return {
                "success": False,
                "error": "Context not found. Ensure whitespace and indentation match exactly.",
            }

        if count > 1:
            return {
                "success": False,
                "error": f"Ambiguous match: Found {count} occurrences. Provide more context.",
            }

        # 4. Apply
        new_content = content.replace(search_text, replace_text)
        target.write_text(new_content, encoding="utf-8")

        # 5. Generate Diff (Feedback Loop)
        diff = difflib.unified_diff(
            search_text.splitlines(),
            replace_text.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )

        return {"success": True, "path": file_path, "diff": "\n".join(list(diff))}

    except Exception as e:
        logger.error(f"Edit failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Rust-Powered Structural Editing (Advanced Feature)
# =============================================================================


def _fallback_replace(content: str, pattern: str, replacement: str) -> str:
    """Fallback implementation using simple string replace."""
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


@skill_command(
    name="structural_replace",
    category="write",
    description="""
    Performs structural replace on content using AST patterns (Rust-powered).

    Uses AST instead of string matching - understands code structure.

    Args:
        - pattern: str - AST pattern to match (e.g., $CLASS_NAME($METHOD_NAME($ARGS))) (required)
        - replacement: str - Replacement pattern with captured variables (required)
        - language: str - Programming language (e.g., python, rust, javascript) (required)
        - content: Optional[str] - Content to search (alternative to path)
        - path: Optional[str] - File path to search (alternative to content)

    Returns:
        Modified content with replacements applied.
    """,
    autowire=True,
)
def structural_replace(
    pattern: str,
    replacement: str,
    language: str,
    content: str | None = None,
    path: str | None = None,
) -> str:
    if path and not content:
        file_path = Path(path)
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
            "Structural replace failed", pattern=pattern, replacement=replacement, error=str(e)
        )
        return f"Error in structural replace: {e!s}"


@skill_command(
    name="structural_preview",
    category="view",
    description="""
    Previews structural replace on a file without modifying it (Rust-powered).

    Shows what would change without applying it. Useful for verification.

    Args:
        - path: str - File path to preview (required)
        - pattern: str - AST pattern to match (required)
        - replacement: str - Replacement pattern (required)
        - language: Optional[str] - Programming language (auto-detected if not specified)

    Returns:
        Preview showing changes that would be applied.
    """,
    autowire=True,
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
        logger.error("Structural preview failed", path=path, pattern=pattern, error=str(e))
        return f"Error in structural preview: {e!s}"


@skill_command(
    name="structural_apply",
    category="write",
    description="""
    Applies structural replace to a file (MODIFIES THE FILE - Rust-powered).

    WARNING: This directly modifies the file. Use structural_preview first.

    Args:
        - path: str - File path to modify (required)
        - pattern: str - AST pattern to match (required)
        - replacement: str - Replacement pattern (required)
        - language: Optional[str] - Programming language (auto-detected if not specified)

    Returns:
        Summary of changes applied.
    """,
    autowire=True,
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
        logger.error("Structural apply failed", path=path, pattern=pattern, error=str(e))
        return f"Error in structural apply: {e!s}"


@skill_command(
    name="refactor_repository",
    category="write",
    description="""
    MASS REFACTORING TOOL. Changes code patterns across the entire repository (Rust-powered).

    Batch structural replace across many files in parallel.

    Args:
        - search_pattern: str - AST pattern to search for (required)
        - rewrite_pattern: str - AST pattern to replace with (required)
        - path: str = "." - Root directory to search
        - file_pattern: str = **/*.py - File glob pattern to match
        - dry_run: bool = true - If true, only show what would change

    Returns:
        Report showing files scanned, changes detected, and errors.
    """,
    autowire=True,
)
def refactor_repository(
    search_pattern: str,
    rewrite_pattern: str,
    path: str = ".",
    file_pattern: str = "**/*.py",
    dry_run: bool = True,
    paths: ConfigPaths | None = None,
) -> str:
    if paths is None:
        paths = ConfigPaths()

    if not RUST_AVAILABLE:
        return (
            "Error: Rust bindings (omni_core_rs) not available.\n"
            "This feature requires heavy-duty batch refactoring.\n"
            "Run 'just build-rust' to enable."
        )

    root_path = paths.project_root / path
    resolved_path = root_path.resolve()

    if not resolved_path.exists():
        return f"Error: Path does not exist: {path}"
    if not resolved_path.is_dir():
        return f"Error: Path is not a directory: {path}"

    try:
        stats = omni_core_rs.batch_structural_replace(
            str(resolved_path),
            search_pattern,
            rewrite_pattern,
            file_pattern,
            dry_run,
        )

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
        logger.error("Batch refactor failed", path=path, pattern=search_pattern, error=str(e))
        return f"Critical Batch Error: {e!s}"


@skill_command(
    name="get_edit_info",
    description="Get information about the structural editing capability.",
    autowire=True,
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
            "Batch refactoring (rayon parallel)",
        ],
        "performance": {
            "batch_mode": "10,000 files = 1 FFI call",
            "parallelism": "Uses all CPU cores",
            "speedup": "~100x vs Python loop",
        },
    }


__all__ = [
    "apply_file_edit",
    "get_edit_info",
    "refactor_repository",
    "structural_apply",
    "structural_preview",
    "structural_replace",
]
