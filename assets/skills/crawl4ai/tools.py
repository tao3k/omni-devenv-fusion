# assets/skills/crawl4ai/tools.py
"""
Crawl4ai Skill - Shim Pattern (Phase 28.1)

This file runs in Omni's main process. It MUST NOT import heavy dependencies
like crawl4ai, playwright, etc. to avoid dependency conflicts.

Heavy imports are delegated to implementation.py running in subprocess.
Uses 'uv run' for cross-platform, self-healing environment management.
"""

import json
import os
import subprocess
from pathlib import Path

from agent.skills.decorators import skill_command

# Skill directory (computed at import time)
SKILL_DIR = Path(__file__).parent
IMPLEMENTATION_SCRIPT = "implementation.py"  # Relative path for uv run


def _run_isolated(command: str, **kwargs) -> str:
    """Execute command in crawl4ai's isolated Python environment.

    Uses 'uv run --directory' for cross-platform, self-healing environment management.

    Args:
        command: Command name to pass to implementation.py
        **kwargs: Arguments to serialize and pass to the command

    Returns:
        Command output or error message
    """

    # Build command: uv run --directory <skill_dir> python implementation.py <command> <json_args>
    cmd = [
        "uv",
        "run",
        "--directory",
        str(SKILL_DIR),
        "-q",  # Quiet mode, reduce uv's own output
        "python",
        IMPLEMENTATION_SCRIPT,
        command,
        json.dumps(kwargs),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,  # 2 minute timeout for web crawling
            env={
                **os.environ,
                "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
            },
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        return f"Error (Exit {e.returncode}):\n{e.stderr}"


@skill_command(
    name="crawl_webpage",
    description="Crawl a webpage and extract its content as Markdown.",
)
def crawl_webpage(url: str, fit_markdown: bool = True) -> str:
    """Crawl a URL and extract its content.

    Args:
        url: The URL to crawl
        fit_markdown: If True, returns fitted Markdown (cleaner). If False, returns raw HTML content.

    Returns:
        Extracted content in Markdown format
    """
    return _run_isolated("crawl", url=url, fit_markdown=fit_markdown)


@skill_command(
    name="crawl_sitemap",
    description="Extract all URLs from a sitemap.xml.",
)
def crawl_sitemap(url: str, max_urls: int = 10) -> str:
    """Extract URLs from a sitemap.

    Args:
        url: The sitemap URL to parse
        max_urls: Maximum number of URLs to return (default: 10)

    Returns:
        JSON array of URLs found in the sitemap
    """
    return _run_isolated("sitemap", url=url, max_urls=max_urls)


@skill_command(
    name="extract_content",
    description="Extract specific content from a webpage using CSS selectors.",
)
def extract_content(url: str, selector: str, attribute: str = "text") -> str:
    """Extract specific content from a webpage using CSS selectors.

    Args:
        url: The URL to crawl
        selector: CSS selector to extract (e.g., 'article p', '#content .item')
        attribute: What to extract - 'text', 'html', or an attribute name

    Returns:
        Extracted content
    """
    return _run_isolated("extract", url=url, selector=selector, attribute=attribute)


def register(mcp) -> None:
    """Register crawl4ai tools with the MCP server."""
    mcp.add_tool(
        crawl_webpage,
        description="Crawl a webpage and extract its content as Markdown.",
    )
    mcp.add_tool(
        crawl_sitemap,
        description="Extract all URLs from a sitemap.xml.",
    )
    mcp.add_tool(
        extract_content,
        description="Extract specific content from a webpage using CSS selectors.",
    )
