#!/usr/bin/env python3
"""
engine.py - Crawl4ai execution engine

This script runs in an isolated uv environment, allowing heavy dependencies
like crawl4ai without polluting the main agent runtime.

Output Format:
    1. First line: JSON metadata (success, url, error, metadata)
    2. Rest: Raw content (markdown) - for direct rendering

Usage:
    uv run --directory ../ python engine.py --url "https://example.com" --fit_markdown true

Or via the isolation runner in tools.py.
"""

import asyncio
import json
import sys
from crawl4ai import AsyncWebCrawler
import fire


async def _crawl_logic(url: str, fit_markdown: bool = True) -> dict:
    """
    Core crawling logic.

    Args:
        url: Target URL to crawl
        fit_markdown: Whether to clean and simplify the markdown

    Returns:
        Dictionary with crawl results and content separately
    """
    try:
        # verbose=False to suppress progress logs
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)

            output = {
                "success": result.success,
                "url": result.url,
                "error": result.error_message or "",
                "metadata": {
                    "title": result.metadata.get("title") if result.metadata else None,
                    "description": result.metadata.get("description") if result.metadata else None,
                },
            }

            # Content is returned separately for direct rendering
            content = result.markdown if fit_markdown else result.raw_markdown

            return output, content

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "metadata": None,
        }, ""


def run_crawl(url: str, fit_markdown: bool = True) -> None:
    """
    Entry point for CLI execution via fire.

    Args:
        url: Target URL to crawl
        fit_markdown: Clean and simplify the markdown output
    """
    result, content = asyncio.run(_crawl_logic(url, fit_markdown))

    # Output format:
    # 1. First line: JSON metadata (to stdout)
    # 2. Rest: Raw content (markdown) - for direct rendering (to stdout)
    # Note: Crawler logs are suppressed by verbose=False
    print(json.dumps(result, ensure_ascii=False))
    if content:
        print(content, end="")


def main():
    """Entry point - fire handles CLI argument parsing automatically."""
    fire.Fire(run_crawl)


if __name__ == "__main__":
    main()
