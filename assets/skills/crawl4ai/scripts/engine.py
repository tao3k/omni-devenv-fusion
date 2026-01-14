#!/usr/bin/env python3
"""
engine.py - Crawl4ai execution engine

This script runs in an isolated uv environment, allowing heavy dependencies
like crawl4ai without polluting the main agent runtime.

Output Format:
    JSON to stdout: {"status": "success", "data": result} or {"status": "error", "error": msg}

Architecture:
    - Heavy imports are lazy-loaded inside functions
    - Uses local skill_script decorator (Shim Pattern) for Rust Scanner
    - Called via JIT Loader's _execute_isolated() method

Usage:
    # Via JIT Loader (automatic uv run):
    loader.execute_tool(record, {"url": "https://example.com"})

    # Direct CLI (for testing):
    uv run --directory . python -c "
    from scripts.engine import crawl_url
    import asyncio
    result = asyncio.run(crawl_url('https://example.com'))
    print(result)
    "
"""

import asyncio
import json
from typing import Optional

# Use local Shim decorator - no agent package dependency
from .utils import skill_script


@skill_script(
    name="crawl_url",
    description="Crawl a web page and extract its content as markdown using Playwright.",
)
async def crawl_url(
    url: str,
    fit_markdown: bool = True,
) -> dict:
    """
    Crawl a webpage and extract content.

    Args:
        url: Target URL to crawl
        fit_markdown: Whether to clean and simplify the markdown (default: True)

    Returns:
        dict with keys:
        - success: bool
        - url: str
        - content: str (markdown)
        - error: str (if success is False)
        - metadata: dict (title, description)
    """
    # Lazy import - only happens in isolated environment
    from crawl4ai import AsyncWebCrawler

    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)

            output = {
                "success": result.success,
                "url": result.url,
                "content": result.markdown if fit_markdown else result.raw_markdown,
                "error": result.error_message or "",
                "metadata": {
                    "title": result.metadata.get("title") if result.metadata else None,
                    "description": result.metadata.get("description") if result.metadata else None,
                },
            }

            return output

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "content": "",
            "error": str(e),
            "metadata": None,
        }


@skill_script(
    name="check_ready",
    description="Check if crawler dependencies are properly installed.",
)
async def check_crawler_ready() -> dict:
    """
    Check if Playwright browsers are installed.

    Returns:
        dict with 'ready' status and any error messages
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browsers = p.chromium.executable_path
            return {"ready": True, "browsers": str(browsers)}
    except Exception as e:
        return {"ready": False, "error": str(e)}


# CLI entry point for direct testing
def main():
    """CLI entry point - reads JSON args from stdin."""
    import sys

    try:
        args = json.loads(sys.stdin.read())
        url = args.get("url", "")
        fit_markdown = args.get("fit_markdown", True)

        result = asyncio.run(crawl_url(url, fit_markdown))
        print(json.dumps({"status": "success", "data": result}, default=str))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, default=str))


if __name__ == "__main__":
    main()
