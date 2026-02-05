---
name: crawl4ai
description: Use when crawling web pages, extracting markdown content, or scraping website data with intelligent chunking and skeleton planning.
metadata:
  author: omni-dev-fusion
  version: "0.2.1"
  source: "https://github.com/unclecode/crawl4ai"
  routing_keywords:
    - "crawl"
    - "web"
    - "scrape"
    - "extract"
    - "fetch"
    - "url"
    - "html"
    - "markdown"
    - "content"
    - "scraper"
    - "crawler"
    - "web scraping"
    - "web crawl"
    - "page content"
    - "web extraction"
  intents:
    - "Crawl a web page"
    - "Extract markdown content"
    - "Scrape website data"
    - "Perform deep crawl"
    - "Get document skeleton/TOC"
    - "Extract specific sections from web page"
---

# crawl4ai

High-performance web crawler with intelligent chunking. Crawls web pages and extracts content as markdown using LLM-based skeleton planning.

## Commands

### `crawl_url` (alias: `webCrawl`)

Crawl a web page with LangGraph workflow and LLM-based intelligent chunking.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | - | Target URL to crawl (required) |
| `action` | str | "smart" | Action mode: "smart", "skeleton", "crawl" |
| `fit_markdown` | bool | true | Clean and simplify markdown output |
| `max_depth` | int | 0 | Maximum crawling depth (0=single page) |
| `return_skeleton` | bool | false | Also return document skeleton (TOC) |
| `chunk_indices` | list[int] | - | List of section indices to extract |

**Action Modes:**
| Mode | Description | Use Case |
|------|-------------|----------|
| `smart` (default) | LLM generates chunk plan, then extracts relevant sections | Large docs where you need specific info |
| `skeleton` | Extract lightweight TOC without full content | Quick overview, decide what to read |
| `crawl` | Return full markdown content | Small pages, complete content needed |

**Examples:**

```python
# Smart crawl with LLM chunking (default)
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com"})

# Skeleton only - get TOC quickly
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "skeleton"})

# Full content crawl
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "crawl"})

# Extract specific sections
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "chunk_indices": [0, 1, 2]})

# Deep crawl (follow links up to depth N)
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "max_depth": 2})

# Get skeleton with full content
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "return_skeleton": true})
```

## Core Concepts

| Topic             | Description                                         | Reference                                         |
| ----------------- | --------------------------------------------------- | ------------------------------------------------- |
| Skeleton Planning | LLM sees TOC (~500 tokens) not full content (~10k+) | [smart-chunking.md](references/smart-chunking.md) |
| Chunk Extraction  | Token-aware section extraction                      | [chunking.md](references/chunking.md)             |
| Deep Crawling     | Multi-page crawling with BFS strategy               | [deep-crawl.md](references/deep-crawl.md)         |

## Best Practices

- Use `skeleton` mode first for large documents to understand structure
- Use `chunk_indices` to extract specific sections instead of full content
- Set `max_depth` > 0 carefully - limits pages crawled to prevent runaway crawling
- Keep `fit_markdown=true` for cleaner output, false for raw content

## Advanced

- Batch multiple URLs with separate calls
- Combine with knowledge tools for RAG pipelines
- Use skeleton + LLM to auto-generate chunk plans for custom extraction
