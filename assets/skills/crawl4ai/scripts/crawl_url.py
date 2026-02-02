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
    category="read",
    description="""
    Crawl a web page and extract its content as markdown using Playwright.

    Supports depth-based crawling to explore linked pages within the same domain.
    The result includes markdown content, metadata, and optionally a list of crawled URLs.

    Args:
        - url: str - Target URL to crawl (required)
        - fit_markdown: bool = true - Clean and simplify the markdown output
        - max_depth: int = 0 - Maximum crawling depth (0 = single page only, 1+ = follow links)

    Returns:
        dict with keys:
        - success: bool - Whether the crawl succeeded
        - url: str - The original URL crawled
        - content: str - Markdown content of the page(s)
        - error: str - Error message if success is False
        - metadata: dict - Page title and description
        - crawled_urls: list[str] - URLs crawled when max_depth > 0
    """,
)
async def crawl_url(
    url: str,
    fit_markdown: bool = True,
    max_depth: int = 0,
) -> dict[str, Any]:
    result = run_skill_command(
        skill_dir=_get_skill_dir(),
        script_name="engine.py",
        args={"url": url, "fit_markdown": fit_markdown, "max_depth": max_depth},
    )
    return result
