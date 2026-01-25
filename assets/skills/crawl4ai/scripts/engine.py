#!/usr/bin/env python3
"""
engine.py - Crawl4ai execution engine

This script runs in an isolated uv environment, allowing heavy dependencies
like crawl4ai without polluting the main agent runtime.

Output Format:
    JSON to stdout: {"success": true, "content": "...", "metadata": {...}}

Architecture:
    - Heavy imports are lazy-loaded inside functions
    - Called via run_skill_command from crawl_url.py

Usage:
    # Via run_skill_command (automatic uv run):
    from omni.foundation.runtime.isolation import run_skill_command
    result = run_skill_command(skill_dir, "engine.py", {"url": "..."})

    # Direct CLI (for testing):
    cd assets/skills/crawl4ai && VIRTUAL_ENV=.venv UV_PROJECT_ENVIRONMENT=.venv uv run python scripts/engine.py --url https://example.com
"""

import asyncio
import io
import json
import sys


async def _crawl_url_impl(
    url: str,
    fit_markdown: bool = True,
) -> dict:
    """
    Internal implementation - runs in isolated uv environment.

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
        result = asyncio.run(_crawl_url_impl(url, fit_markdown))
        print(json.dumps(result, default=str))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, default=str))


if __name__ == "__main__":
    main()
