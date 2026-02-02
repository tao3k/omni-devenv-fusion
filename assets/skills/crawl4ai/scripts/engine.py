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
    max_depth: int = 0,
) -> dict:
    """
    Internal implementation - runs in isolated uv environment.

    Args:
        url: Target URL to crawl
        fit_markdown: Whether to clean and simplify the markdown (default: True)
        max_depth: Maximum crawling depth (0 = single page only, >0 = crawl linked pages)

    Returns:
        dict with keys:
        - success: bool
        - url: str
        - content: str (markdown)
        - error: str (if success is False)
        - metadata: dict (title, description)
        - crawled_urls: list[str] (urls crawled when max_depth > 0)
    """
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

    # Capture stdout during crawl to prevent progress bars from polluting JSON output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            if max_depth > 0:
                # Crawl with depth - use deep crawl strategy
                config = CrawlerRunConfig(
                    deep_crawl_strategy=BFSDeepCrawlStrategy(
                        max_depth=max_depth,
                        include_external=False,  # Stay within same domain
                        max_pages=20,  # Limit for efficiency
                    ),
                )
                result = await crawler.arun(url=url, config=config)
                # Deep crawl returns a list of CrawlResult objects
                results = result if isinstance(result, list) else [result]
                # Combine markdown from all pages
                all_content = []
                all_urls = []
                for r in results:
                    if r.success:
                        all_content.append(r.markdown if fit_markdown else r.raw_markdown)
                        all_urls.append(r.url)
                combined_content = "\n\n---\n\n".join(all_content)
                first_result = results[0] if results else None
                success = len([r for r in results if r.success]) > 0
                error_msg = first_result.error_message if first_result else ""
                metadata = first_result.metadata if first_result else None
                sys.stdout = old_stdout  # Restore stdout before return
                return {
                    "success": success,
                    "url": url,
                    "content": combined_content,
                    "error": error_msg,
                    "metadata": {
                        "title": metadata.get("title") if metadata else None,
                        "description": metadata.get("description") if metadata else None,
                    },
                    "crawled_urls": all_urls if all_urls else None,
                }
            else:
                # Single page crawl
                result = await crawler.arun(url=url)

        # Discard captured stdout (progress bars)
        sys.stdout = old_stdout

        # Collect crawled URLs if available
        crawled_urls = []
        if hasattr(result, "crawled_urls") and result.crawled_urls:
            crawled_urls = result.crawled_urls
        elif hasattr(result, "downloaded_urls") and result.downloaded_urls:
            crawled_urls = result.downloaded_urls

        return {
            "success": result.success,
            "url": result.url,
            "content": result.markdown if fit_markdown else result.raw_markdown,
            "error": result.error_message or "",
            "metadata": {
                "title": result.metadata.get("title") if result.metadata else None,
                "description": result.metadata.get("description") if result.metadata else None,
            },
            "crawled_urls": crawled_urls if crawled_urls else None,
        }

    except Exception as e:
        sys.stdout = old_stdout
        return {
            "success": False,
            "url": url,
            "content": "",
            "error": str(e),
            "metadata": None,
            "crawled_urls": None,
        }


def main():
    """CLI entry point - supports both stdin JSON and command line args."""
    import argparse

    parser = argparse.ArgumentParser(description="Crawl4AI Engine")
    parser.add_argument("--url", type=str, help="URL to crawl")
    parser.add_argument(
        "--fit_markdown", type=str, default="true", help="Clean markdown (true/false)"
    )
    parser.add_argument(
        "--max_depth", type=int, default=0, help="Maximum crawling depth (0=single page)"
    )
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()

    # Parse URL and fit_markdown
    url = ""
    fit_markdown = True
    max_depth = 0

    if args.stdin and not sys.stdin.isatty():
        # Read JSON from stdin (for uv run with pipe)
        try:
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                json_args = json.loads(stdin_data)
                url = json_args.get("url", "")
                fit_markdown = json_args.get("fit_markdown", True)
                max_depth = json_args.get("max_depth", 0)
        except json.JSONDecodeError:
            pass
    else:
        # Use command line args (for run_skill_command)
        url = args.url or ""
        fit_markdown = args.fit_markdown.lower() == "true" if args.fit_markdown else True
        max_depth = args.max_depth or 0

    if not url:
        print(json.dumps({"success": False, "error": "Missing URL"}, default=str))
        return

    try:
        result = asyncio.run(_crawl_url_impl(url, fit_markdown, max_depth))
        print(json.dumps(result, default=str))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, default=str))


if __name__ == "__main__":
    main()
