# crawl4ai

High-performance web crawler with intelligent chunking for Omni-Dev-Fusion.

## Quick Start

```bash
cd assets/skills/crawl4ai
uv run pytest tests/test_graph.py -v
```

## Overview

Crawl web pages and extract markdown content using the **Skeleton Planning Pattern**:

- LLM sees TOC (~500 tokens) instead of full content (~10k+)
- Smart chunk extraction based on document structure
- Token-efficient for large documents

## Commands

| Command                         | Description                            |
| ------------------------------- | -------------------------------------- |
| `crawl_url` (alias: `webCrawl`) | Main crawl command with smart chunking |

## Usage

```python
# Smart crawl with LLM chunking
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com"})

# Skeleton only
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "skeleton"})

# Extract specific sections
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "chunk_indices": [0, 1, 2]})

# Deep crawl
@omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "max_depth": 2})
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main MCP Env                            │
│  ┌─────────────────┐    ┌─────────────────────────────┐   │
│  │ crawl_url.py    │───▶│ LLM Chunk Planning         │   │
│  │ (MCP entry)     │    │ (system_prompt + skeleton) │   │
│  └─────────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ uv run engine.py --action smart --chunk_plan <JSON>
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Isolated .venv                            │
│  ┌─────────────────┐    ┌─────────────────────────────┐   │
│  │ engine.py       │───▶│ crawl4ai + chunk extraction │   │
│  │ (Heavy deps)    │    │                             │   │
│  └─────────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File                   | Purpose                           |
| ---------------------- | --------------------------------- |
| `scripts/crawl_url.py` | MCP interface (main env with LLM) |
| `scripts/engine.py`    | Crawl execution (isolated .venv)  |
| `scripts/graph.py`     | Skeleton utilities & prompts      |
| `scripts/references/`  | Detailed documentation            |
| `tests/test_graph.py`  | Unit tests                        |

## Reference Docs

- [Smart Chunking Strategy](scripts/references/smart-chunking.md) - Skeleton Planning Pattern
- [Chunk Extraction](scripts/references/chunking.md) - Line-based extraction API
- [Deep Crawling](scripts/references/deep-crawl.md) - Multi-page crawling

## Testing

```bash
# Run tests
uv run pytest tests/ -v

# Test isolation
VIRTUAL_ENV=.venv UV_PROJECT_ENVIRONMENT=.venv uv run python scripts/engine.py --url https://example.com --action skeleton
```
