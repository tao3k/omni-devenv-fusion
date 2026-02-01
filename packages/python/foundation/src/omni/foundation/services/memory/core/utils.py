# core/utils.py
"""
Memory utility functions.

Shared utilities for memory operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def format_decision(decision: dict[str, Any]) -> str:
    """Format a decision for storage as Markdown ADR."""
    from datetime import datetime

    lines = [
        f"# Decision: {decision.get('title', 'Untitled')}",
        f"Date: {decision.get('date', datetime.now().isoformat())}",
        f"Author: {decision.get('author', 'Claude')}",
        "",
        "## Problem",
        decision.get("problem", "N/A"),
        "",
        "## Solution",
        decision.get("solution", "N/A"),
        "",
        "## Rationale",
        decision.get("rationale", "N/A"),
        "",
        "## Status",
        decision.get("status", "open"),
    ]
    return "\n".join(lines)


def parse_decision(content: str) -> dict[str, str]:
    """Parse a Markdown ADR back to a dict."""
    decision: dict[str, str] = {}
    lines = content.split("\n")
    current_section: str | None = None
    section_content: list[str] = []

    for line in lines:
        if line.startswith("# Decision:"):
            decision["title"] = line.replace("# Decision:", "").strip()
        elif line.startswith("Date:"):
            decision["date"] = line.replace("Date:", "").strip()
        elif line.startswith("Author:"):
            decision["author"] = line.replace("Author:", "").strip()
        elif line.startswith("## "):
            if current_section and section_content:
                decision[current_section] = "\n".join(section_content).strip()
            current_section = line.replace("## ", "").lower().strip()
            section_content = []
        elif current_section in ["problem", "solution", "rationale", "status"]:
            section_content.append(line)

    if current_section and section_content:
        decision[current_section] = "\n".join(section_content).strip()

    return decision


def init_memory_dir(dir_path: Path) -> bool:
    """Initialize the memory directory structure."""
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "decisions").mkdir(exist_ok=True)
        (dir_path / "tasks").mkdir(exist_ok=True)
        (dir_path / "context").mkdir(exist_ok=True)
        (dir_path / "active_context").mkdir(exist_ok=True)
        return True
    except Exception:
        return False
