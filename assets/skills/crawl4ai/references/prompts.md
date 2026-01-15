# Crawl4ai Skill Prompts

## When to Use

Use the `crawl4ai` skill when you need to:

- Extract content from a URL
- Scrape web pages for information
- Get webpage content as clean markdown

## Routing Keywords

- `crawl`, `scrape`, `web`, `fetch`, `url`, `website`, `page`

## Examples

### User Request

```
Can you get the content from https://example.com?
```

### Claude Invocation

```
@omni("skill.run crawl4ai.crawl_webpage url='https://example.com'")
```

### Result

Returns the page content as markdown that can be used for further analysis.

## Limitations

- Cannot crawl pages behind authentication
- Respects robots.txt
- May not work well with heavily JavaScript-rendered pages
- Rate limiting applies to avoid overwhelming target servers

## Best Practices

1. Always verify the URL is accessible before crawling
2. Use `fit_markdown=True` for cleaner output
3. Handle errors gracefully - some pages may be unavailable
4. Consider the target site's terms of service
