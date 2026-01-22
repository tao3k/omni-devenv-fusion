"""
crawl4ai/scripts/ - Crawl4ai Skill Interface

This module exposes command interfaces for the main agent.
Commands are executed via Sidecar Execution Pattern (isolated subprocess).

IMPORTANT: These function signatures are scanned by Rust AST Scanner
for command discovery. The actual implementation is in engine.py.
"""

from typing import Any
from omni.core.skills.script_loader import skill_command


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
    # Delegate to subprocess execution
    from . import isolation

    return await isolation.execute_crawl(url, fit_markdown=fit_markdown)


@skill_command(
    name="check_crawler_ready",
    description="Check if the crawler skill is properly configured and ready.",
)
async def check_crawler_ready() -> dict[str, Any]:
    """
    Check if Playwright browsers are installed and crawler is ready.

    Returns:
        dict with 'ready' status and any error messages
    """
    from . import isolation

    return await isolation.execute_check_ready()
