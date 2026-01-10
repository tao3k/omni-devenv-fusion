"""
tools.py - Crawl4ai Skill Interface

This module provides a clean interface to the crawl4ai web crawler skill.

Architecture: Sidecar Execution Pattern via Swarm
- This file is loaded by the main agent (lightweight, no heavy imports)
- Actual crawling happens in scripts/engine.py via Swarm isolation
- Heavy dependency (crawl4ai) lives only in this skill's environment

Usage:
    @omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
"""

from typing import Any, Callable, Optional

from agent.skills.decorators import skill_command
from agent.core.swarm import get_swarm


@skill_command
async def crawl_webpage(
    url: str,
    fit_markdown: bool = True,
    log_handler: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Crawl a webpage and extract its content as markdown.

    Uses Sidecar Execution Pattern via Swarm:
    - Runs crawl4ai in an isolated environment
    - No heavy dependencies in the main agent runtime

    Args:
        url: Target URL to crawl
        fit_markdown: Clean and simplify the markdown (default: True)
        log_handler: Optional callback for logging messages

    Returns:
        dict with keys:
        - success: bool
        - url: str (the crawled URL)
        - content: str (extracted markdown content)
        - error: str (if success is False)
        - metadata: dict (title, description if available)

    Example:
        >>> result = crawl_webpage("https://example.com", fit_markdown=True)
        >>> if result.success:
        ...     print(result["content"])
    """
    # Swarm handles async execution internally
    return await get_swarm().execute_skill(
        skill_name="crawl4ai",
        command="engine.py",
        args={"url": url, "fit_markdown": fit_markdown},
        mode="sidecar_process",
        timeout=30,  # 30 second timeout for web crawling
        log_handler=log_handler,
    )


@skill_command
async def check_crawler_ready() -> dict:
    """
    Check if the crawler skill is properly configured and ready.

    Returns:
        dict with 'ready' status and any error messages
    """
    return get_swarm().check_skill_dependencies("crawl4ai")
