"""
omni.foundation.utils.formatting - String & Output Formatting Utilities

Provides unified logic for:
- Truncating large content (logs protection)
- Sanitizing tool arguments (privacy & noise reduction)
"""

from typing import Any

# Fields that typically contain massive text/code
LARGE_FIELDS = {
    "content",
    "text",
    "code",
    "markdown",
    "body",
    "file_content",
    "data",
    "source_code",
    "result",
    "analysis",
    "plan",
    "patch",
}


def one_line_preview(value: Any, max_len: int = 80) -> str:
    """Create a clean one-line preview of any content.

    Features:
    - Flattens newlines to spaces
    - Truncates with length indicator (+N chars)
    - Handles None/Objects gracefully
    """
    if value is None:
        return "None"

    s_val = str(value)

    # Flatten: replace newlines with spaces to keep log one-line
    flat_val = s_val.replace("\n", " ").replace("\r", "")
    flat_val = " ".join(flat_val.split())  # Compress multiple spaces

    if len(flat_val) <= max_len:
        return flat_val

    # Truncate
    preview = flat_val[:max_len]
    remaining = len(s_val) - max_len
    return f"{preview}... (+{remaining} chars)"


def sanitize_tool_args(args: dict[str, Any]) -> str:
    """Format tool arguments for logging, aggressively compressing large fields.

    Returns:
        String like: 'path="src/main.py", content="def main():..." (+500 chars)'
    """
    if not args:
        return ""

    clean_items = []

    for k, v in args.items():
        if k in LARGE_FIELDS:
            # Allow slightly longer preview for content fields
            v_display = one_line_preview(v, max_len=80)
            clean_items.append(f'{k}="{v_display}"')
        else:
            # Strict limit for metadata fields
            v_display = one_line_preview(v, max_len=30)
            clean_items.append(f"{k}={v_display}")

    return ", ".join(clean_items)
