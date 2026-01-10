---
name: crawl4ai
version: 0.1.0
description: High-performance web crawler skill using Sidecar Execution Pattern
author: Omni Team
routing_keywords: [crawl, scrape, web, fetch, scrape]
execution_mode: subprocess
intents:
  - "Crawl a webpage and extract its content"
  - "Fetch website content as markdown"
  - "Scrape web pages for information"
---

# Crawl4ai Skill

High-performance web crawler using the Sidecar Execution Pattern for dependency isolation.

## Architecture

This skill demonstrates **Sidecar Execution Pattern**:

- `tools.py`: Lightweight interface (loaded by main agent, no heavy imports)
- `scripts/engine.py`: Actual crawler implementation (runs in isolated uv environment)
- `pyproject.toml`: Skill-specific dependencies (crawl4ai, fire, pydantic)

The main agent never imports crawl4ai directly. Instead, it uses `common.isolation.run_skill_script()` to execute the crawler in a subprocess with its own isolated environment.

## Commands

### crawl_webpage

Crawl a webpage and extract its content as markdown.

```python
@omni("skill.run crawl4ai.crawl_webpage url='https://example.com'")
```

**Parameters:**

- `url` (str, required): Target URL to crawl
- `fit_markdown` (bool, default: True): Clean and simplify the markdown

**Returns:**

```python
{
    "success": True,
    "url": "https://example.com",
    "markdown": "# Example\n\nContent...",
    "metadata": {"title": "Example", "description": "..."},
    "error": None
}
```

### check_crawler_ready

Check if the crawler skill is properly configured.

```python
@omni("skill.run crawl4ai.check_crawler_ready")
```

## Setup

Dependencies are automatically managed by uv:

```bash
cd assets/skills/crawl4ai
uv sync  # Installs crawl4ai and its dependencies
```

## Usage Example

```python
# In conversation with Claude
Please crawl https://github.com and give me the main content as markdown.

# Claude will invoke:
# @omni("skill.run crawl4ai.crawl_webpage url='https://github.com'")
```

## Why Sidecar Pattern?

1. **Zero Pollution**: Main agent doesn't need crawl4ai, playwright, or other heavy deps
2. **Version Isolation**: Each skill can use different versions of the same library
3. **Hot Swappable**: Skills can be added/removed without restarting the agent
4. **Security**: Compromised skill code has limited blast radius
