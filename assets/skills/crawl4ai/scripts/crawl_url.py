"""
crawl4ai/scripts/ - Crawl4ai Skill Interface

This module exposes command interfaces for the main agent.
Commands are executed via Foundation's Isolation Pattern.

IMPORTANT: These function signatures are scanned by Rust AST Scanner
for command discovery. The actual implementation is in engine.py.
"""

from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.runtime.isolation import run_skill_command


def _get_skill_dir() -> Path:
    """Get the skill directory for isolation."""
    return Path(__file__).parent.parent


@skill_command(
    name="crawl_url",
    description="Crawl a web page and extract its content as markdown using Playwright.",
)
async def crawl_url(
    url: str,
    fit_markdown: bool = True,
) -> dict[str, Any]:
    """
    Crawl a webpage and extract content as markdown.

    Args:
        url: Target URL to crawl
        fit_markdown: Whether to clean and simplify the markdown (default: True)

    Returns:
        dict with keys: success, url, content, error, metadata
    """
    result = run_skill_command(
        skill_dir=_get_skill_dir(),
        script_name="engine.py",
        args={"url": url, "fit_markdown": fit_markdown},
    )
    return result
