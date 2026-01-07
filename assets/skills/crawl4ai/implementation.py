# assets/skills/crawl4ai/implementation.py
"""
Crawl4ai Skill Implementation (Phase 28.1)

This file runs in a subprocess with its own isolated Python environment.
It CAN import crawl4ai, playwright, and other heavy dependencies safely.

Communication protocol:
  python implementation.py <command> <args_json>

Commands:
  crawl <args_json>    - Crawl a URL and return Markdown
  sitemap <args_json>  - Extract URLs from sitemap
  extract <args_json>  - Extract content using CSS selectors
"""

import sys
import json
import asyncio
from crawl4ai import AsyncWebCrawler


async def crawl(url: str, fit_markdown: bool = True) -> str:
    """Crawl a URL and extract content as Markdown."""
    from crawl4ai import CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    # Configure markdown generation
    if fit_markdown:
        # Use pruning filter for content filtering
        content_filter = PruningContentFilter(threshold=0.48, threshold_type="fixed")
    else:
        # No filtering
        content_filter = None

    md_generator = DefaultMarkdownGenerator(content_filter=content_filter)
    config = CrawlerRunConfig(markdown_generator=md_generator)

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)

        # result.markdown is StringCompatibleMarkdown
        # With filter configured, it has raw_markdown and fit_markdown
        if hasattr(result.markdown, "fit_markdown") and result.markdown.fit_markdown:
            return result.markdown.fit_markdown
        else:
            return str(result.markdown)


async def sitemap(url: str, max_urls: int = 10) -> str:
    """Extract URLs from a sitemap."""
    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)

        # Try to extract sitemap URLs from the markdown
        if hasattr(result, "links") and result.links:
            urls = [link["href"] for link in result.links[:max_urls] if link.get("href")]
            return json.dumps(urls)

        # Fallback: try to parse from raw content
        raw = result.markdown.raw
        import re

        url_pattern = r"<loc>(.*?)</loc>"
        urls = re.findall(url_pattern, raw)[:max_urls]
        return json.dumps(urls)


async def extract(url: str, selector: str, attribute: str = "text") -> str:
    """Extract content using CSS selectors."""
    from crawl4ai import AsyncWebCrawler
    from bs4 import BeautifulSoup

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        html = result.html.raw if hasattr(result.html, "raw") else ""

        if not html:
            return json.dumps({"error": "Could not fetch HTML content"})

        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(selector)

        if not elements:
            return json.dumps({"error": f"No elements found for selector: {selector}"})

        results = []
        for elem in elements:
            if attribute == "text":
                text = elem.get_text(strip=True)
                results.append(text)
            elif attribute == "html":
                results.append(str(elem))
            else:
                # Extract an attribute (e.g., 'href', 'src')
                val = elem.get(attribute)
                results.append(val)

        return json.dumps(results)


def main():
    """Main entry point - parse command and execute."""
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: python implementation.py <command> <args_json>"}))
        sys.exit(1)

    command = sys.argv[1]
    args = json.loads(sys.argv[2])

    try:
        if command == "crawl":
            url = args.get("url")
            if not url:
                print(json.dumps({"error": "Missing required argument: url"}))
                sys.exit(1)
            result = asyncio.run(crawl(url, args.get("fit_markdown", True)))
            print(result)

        elif command == "sitemap":
            url = args.get("url")
            if not url:
                print(json.dumps({"error": "Missing required argument: url"}))
                sys.exit(1)
            result = asyncio.run(sitemap(url, args.get("max_urls", 10)))
            print(result)

        elif command == "extract":
            url = args.get("url")
            selector = args.get("selector")
            if not url or not selector:
                print(json.dumps({"error": "Missing required arguments: url, selector"}))
                sys.exit(1)
            result = asyncio.run(extract(url, selector, args.get("attribute", "text")))
            print(result)

        else:
            print(json.dumps({"error": f"Unknown command: {command}"}))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
