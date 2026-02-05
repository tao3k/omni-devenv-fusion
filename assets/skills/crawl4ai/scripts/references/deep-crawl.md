# Deep Crawling

## Overview

Deep crawling crawls multiple pages by following links from the starting URL. Uses BFS (Breadth-First Search) strategy with configurable depth.

## Usage

Set `max_depth` parameter:

```python
@omni("crawl4ai.CrawlUrl", {
    "url": "https://example.com/docs",
    "max_depth": 2  # Crawl 2 levels deep
})
```

## Depth Levels

| max_depth | Pages Crawled             | Description                |
| --------- | ------------------------- | -------------------------- |
| 0         | 1                         | Single page only (default) |
| 1         | Start + direct links      | One level of links         |
| 2         | Start + links + sub-links | Two levels of links        |
| N         | BFS up to depth N         | Configurable depth         |

## Configuration Options

### `include_external`

Control whether to follow external links:

```python
# Only internal links (default)
"include_external": false

# Follow external links too
"include_external": true  # Use with caution!
```

### `max_pages`

Limit total pages crawled:

```python
"max_pages": 20  # Stop after 20 pages regardless of depth
```

## Output Format

Deep crawl returns combined markdown from all pages:

```json
{
  "success": true,
  "url": "https://example.com",
  "content": "Page 1 content...\n\n---\n\nPage 2 content...",
  "crawled_urls": [
    "https://example.com",
    "https://example.com/page1",
    "https://example.com/page2"
  ],
  "metadata": {
    "title": "Main Page Title"
  }
}
```

## Best Practices

1. **Start Small**: Begin with `max_depth=1` to verify correct pages are crawled

2. **Set Limits**: Always set `max_pages` to prevent runaway crawling:

   ```python
   "max_depth": 2,
   "max_pages": 20
   ```

3. **Filter URLs**: If needed, pre-filter starting URL to a specific section

4. **Check Crawled URLs**: Verify `crawled_urls` matches expectations

## Limitations

- Does not respect robots.txt by default
- No rate limiting between requests
- May crawl duplicate content from similar pages
- External links can expand scope dramatically

## When to Use Deep Crawl

| Use Case                  | Recommendation                  |
| ------------------------- | ------------------------------- |
| Documentation site        | `max_depth: 2`, `max_pages: 50` |
| Blog archives             | `max_depth: 1`, `max_pages: 20` |
| Single article + comments | `max_depth: 0`                  |
| GitHub repo README        | `max_depth: 0`                  |

## Alternative: Multiple Single Crawls

For more control, crawl pages individually:

```python
# Instead of deep crawl
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
]

for url in urls:
    @omni("crawl4ai.CrawlUrl", {"url": url})
```

This allows per-page error handling and custom chunking strategies.
