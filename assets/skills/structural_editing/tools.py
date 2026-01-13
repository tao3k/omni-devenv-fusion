"""
agent/skills/structural_editing/tools.py
Phase 52: The Surgeon - Structural Code Refactoring

Provides AST-based code modification using ast-grep patterns.
AX Philosophy: "Surgical precision" - modify exactly what you mean, not fuzzy matches.

Features:
- structural_replace: Replace patterns in content strings
- structural_preview: Preview changes on files (no modification)
- structural_apply: Apply changes to files (modifies files)
- Diff generation showing exact changes
- Multi-language support (Python, Rust, JavaScript, TypeScript)

Part of Phase 52: The Surgeon (CCA-Aligned Code Modification)
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
        "version": "1.0.0",
        "rust_available": RUST_AVAILABLE,
        "supported_languages": ["python", "rust", "javascript", "typescript"],
        "features": [
            "AST-based pattern matching",
            "Variable capture ($ARGS, $NAME, etc.)",
            "Unified diff generation",
            "Preview before apply workflow",
        ],
        "phase": "Phase 52: The Surgeon",
    }
