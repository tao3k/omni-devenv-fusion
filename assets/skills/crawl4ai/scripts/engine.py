#!/usr/bin/env python3
"""
engine.py - Crawl4ai execution engine

This script runs in an isolated uv environment, allowing heavy dependencies
like crawl4ai without polluting the main agent runtime.

Output Format:
    JSON to stdout: {"success": true, "content": "...", "metadata": {...}}

Architecture:
    - Heavy imports are lazy-loaded inside functions
    - Uses local skill_command decorator (Shim Pattern) for Rust Scanner
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
import io
import json
import sys

# Use absolute import for uv run compatibility
try:
    from .utils import skill_command
except ImportError:
    from utils import skill_command


@skill_command(
    name="crawl_url",
    category="read",
    description="""
    Crawl a web page and extract its content as markdown using Playwright.

    Args:
        - url: str - Target URL to crawl (required)
        - fit_markdown: bool = true - Whether to clean and simplify the markdown

    Returns:
        Dictionary with success, url, content, error, and metadata (title, description).
    """,
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

    # Capture stdout during crawl to prevent progress bars from polluting JSON output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)

        # Discard captured stdout (progress bars)
        sys.stdout = old_stdout

        return {
            "success": result.success,
            "url": result.url,
            "content": result.markdown if fit_markdown else result.raw_markdown,
            "error": result.error_message or "",
            "metadata": {
                "title": result.metadata.get("title") if result.metadata else None,
                "description": result.metadata.get("description") if result.metadata else None,
            },
        }

    except Exception as e:
        sys.stdout = old_stdout
        return {
            "success": False,
            "url": url,
            "content": "",
            "error": str(e),
            "metadata": None,
        }


@skill_command(
    name="check_crawler_ready",
    category="read",
    description="""
    Check if the crawler skill is properly configured and Playwright browsers are installed.

    Args:
        - None

    Returns:
        Dictionary with ready status and browsers info or error message.
    """,
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


def main():
    """CLI entry point - supports both stdin JSON and command line args."""
    import argparse

    parser = argparse.ArgumentParser(description="Crawl4AI Engine")
    parser.add_argument("--url", type=str, help="URL to crawl")
    parser.add_argument(
        "--fit_markdown", type=str, default="true", help="Clean markdown (true/false)"
    )
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()

    # Parse URL and fit_markdown
    url = ""
    fit_markdown = True

    if args.stdin and not sys.stdin.isatty():
        # Read JSON from stdin (for uv run with pipe)
        try:
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                json_args = json.loads(stdin_data)
                url = json_args.get("url", "")
                fit_markdown = json_args.get("fit_markdown", True)
        except json.JSONDecodeError:
            pass
    else:
        # Use command line args (for run_skill_command)
        url = args.url or ""
        fit_markdown = args.fit_markdown.lower() == "true" if args.fit_markdown else True

    if not url:
        print(json.dumps({"success": False, "error": "Missing URL"}, default=str))
        return

    try:
        result = asyncio.run(crawl_url(url, fit_markdown))
        print(json.dumps(result, default=str))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, default=str))


if __name__ == "__main__":
    main()
