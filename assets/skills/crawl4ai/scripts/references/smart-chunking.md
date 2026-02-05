# Smart Chunking Strategy

## Overview

The **Skeleton Planning Pattern** is the core intelligent chunking strategy used by crawl4ai. Instead of dumping entire document content to the LLM (~10k+ tokens), we:

1. Extract lightweight TOC/skeleton (~500 tokens)
2. LLM analyzes structure and decides what to extract
3. Execute targeted chunk extraction based on LLM plan

```
┌─────────────────────────────────────────────────────────────┐
│                    Document (~50KB)                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Section 1: Intro (~5KB)                           │  │
│  │  Section 2: Overview (~8KB)                       │  │
│  │  Section 3: Deep Dive (~15KB)                      │  │
│  │  Section 4: Examples (~12KB)                       │  │
│  │  Section 5: FAQ (~5KB)                             │  │
│  │  Section 6: API Ref (~5KB)                         │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Skeleton (~500 tokens)                   │
│  - [0] Introduction                                        │
│  - [1] Getting Started                                    │
│  - [2] Core Concepts      ◄── LLM decides what's relevant │
│  - [3] Advanced Usage                                        │
│  - [4] API Reference                                       │
│  - [5] FAQ                                                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ LLM Planning
┌─────────────────────────────────────────────────────────────┐
│                  Chunk Plan JSON                            │
│  {                                                         │
│    "chunks": [                                             │
│      {"chunk_id": 0, "section_indices": [2, 3],            │
│       "reason": "Core concepts and advanced usage"},        │
│      {"chunk_id": 1, "section_indices": [4],                │
│       "reason": "API reference for implementation"}        │
│    ]                                                       │
│  }                                                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Extracted Content (~3KB)                   │
│  Only relevant sections, no token waste                     │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Skeleton Extraction

```python
from engine import extract_skeleton

skeleton_result = extract_skeleton(markdown_content)
# Returns:
# {
#   "skeleton": [
#     {"index": 0, "level": 1, "title": "Introduction", "line_start": 0, "position": 0.0},
#     {"index": 1, "level": 1, "title": "Getting Started", "line_start": 45, "position": 0.15},
#     ...
#   ],
#   "stats": {
#     "total_chars": 50000,
#     "total_tokens_approx": 12500,
#     "header_count": 20,
#     "max_depth": 3
#   }
# }
```

### 2. LLM Chunk Planning

The LLM receives skeleton and generates optimal chunk plan:

```json
{
  "chunks": [
    {
      "chunk_id": 0,
      "section_indices": [0, 1, 2],
      "reason": "Introduction and setup context"
    },
    {
      "chunk_id": 1,
      "section_indices": [5, 6, 7],
      "reason": "API implementation details"
    }
  ]
}
```

### 3. Targeted Extraction

```python
from engine import extract_chunk

chunk = extract_chunk(
    markdown_content,
    line_start=skeleton[5]["line_start"],
    line_end=skeleton[7]["line_end"]
)
```

## Token Optimization

| Document Size | Full Content | Skeleton Only | Smart Chunking   |
| ------------- | ------------ | ------------- | ---------------- |
| 10KB          | ~2,500 tok   | ~200 tok      | ~500-800 tok     |
| 50KB          | ~12,500 tok  | ~500 tok      | ~1,000-2,000 tok |
| 100KB         | ~25,000 tok  | ~800 tok      | ~2,000-3,000 tok |

## When to Use

| Scenario                  | Recommended Mode        |
| ------------------------- | ----------------------- |
| Quick document overview   | `skeleton`              |
| RAG with specific queries | `smart` + chunk_indices |
| Complete content needed   | `crawl`                 |
| Batch processing          | `crawl` + post-process  |
| Large technical docs      | `smart`                 |

## Integration with crawl_url

```python
# In crawl_url.py (main MCP env with LLM)
from graph import CHUNKING_PLANNER_PROMPT

# 1. Crawl and get skeleton
result = await crawler.arun(url=url)
skeleton = extract_skeleton(result.markdown)

# 2. LLM generates chunk plan
response = llm.complete(
    system_prompt=CHUNKING_PLANNER_PROMPT.format(
        title=metadata.get("title", ""),
        section_count=len(skeleton),
        skeleton=json.dumps(skeleton[:20])
    ),
    user_query="What sections are most relevant for: " + user_intent
)

# 3. Pass plan to isolated engine for extraction
chunk_plan = json.loads(response.content)
final_content = run_skill_command("crawl4ai", "engine.py", {
    "url": url,
    "action": "smart",
    "chunk_plan": chunk_plan
})
```
