"""
xml.py - Shared XML helpers for tracer-related modules.
"""

from __future__ import annotations

import re


def escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def extract_tag(xml: str, tag: str) -> str:
    """Extract content from a simple XML tag."""
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_attr(xml: str, tag: str, attr: str) -> str:
    """Extract an attribute from a tag opening element."""
    match = re.search(rf'<{tag}\b[^>]*\b{attr}="([^"]+)"[^>]*>', xml)
    return match.group(1).strip() if match else ""


__all__ = [
    "escape_xml",
    "extract_tag",
    "extract_attr",
]
