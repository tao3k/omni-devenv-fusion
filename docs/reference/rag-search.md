# RAG Search Reference

> High-performance semantic search with caching and hybrid search capabilities.

## Overview

RAG (Retrieval-Augmented Generation) Search provides intelligent tool/command discovery through:

- **Semantic Search**: Vector similarity matching for natural language queries
- **Search Cache**: LRU caching with TTL to reduce latency
- **Hybrid Search**: Combines semantic and keyword matching for improved recall

Knowledge-layer retrieval follows the same explicit split:

- `vector_search(vector, limit)` for semantic-only retrieval
- `text_search(query_text, query_vector, limit)` for hybrid retrieval

Normalization invariants applied by the Python retrieval namespace:

- Threshold filtering: drop rows below `score_threshold`
- Deterministic dedupe: keep the highest score per logical record
- Stable ranking: always sort by descending score after normalization

Dedupe key policy:

1. Prefer `id` when present
2. Fallback to `content` for rows without durable ids

## Components

### SearchCache

LRU cache for search results with automatic expiration.

```python
from omni.core.router import SearchCache

# Initialize with custom settings
cache = SearchCache(max_size=1000, ttl=300)  # 1000 entries, 5 min TTL

# Cache results
cache.set("git commit", results)

# Retrieve cached results
results = cache.get("git commit")

# Clear cache
cache.clear()
```

**Features**:

- LRU eviction when cache is full
- TTL-based automatic expiration
- Thread-safe operations
- Statistics via `cache.stats()`

### HybridSearch

Combines semantic (vector) and keyword search for better relevance.

```python
from omni.core.router.hybrid_search import HybridSearch, KeywordIndexer

# Create keyword indexer
keyword_indexer = KeywordIndexer()
keyword_indexer.index("cmd_1", "Git commit message", {"type": "command"})

# Create hybrid search
search = HybridSearch(
    semantic_indexer=vector_store,
    keyword_indexer=keyword_indexer,
    semantic_weight=0.7,  # 70% semantic, 30% keyword
    keyword_weight=0.3,
)

# Execute hybrid search
results = await search.search("commit code", limit=5)
```

**Scoring Formula**:

```
combined_score = semantic_weight * semantic_score + keyword_weight * keyword_score
```

### SkillIndexer

Builds semantic index from skill definitions.

```python
from omni.core.router import SkillIndexer

indexer = SkillIndexer(vector_store)
await indexer.build_index(skills)
results = await indexer.search("git commit", limit=10)
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User Query    │────▶│  HybridSearch    │────▶│  Results        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌─────────────────┐              ┌─────────────────┐
    │ Semantic Search │              │ Keyword Search  │
    │ (Vector Store)  │              │ (KeywordIndexer)│
    └─────────────────┘              └─────────────────┘
               │                               │
               └───────────────┬───────────────┘
                               ▼
                      ┌─────────────────┐
                      │   SearchCache   │
                      │  (LRU + TTL)    │
                      └─────────────────┘
```

## Usage Patterns

### Basic Routing

```python
from omni.core.router import OmniRouter

router = OmniRouter()
await router.initialize(skills)
result = await router.route("commit the changes")
```

### With Caching

```python
from omni.core.router import SemanticRouter, SearchCache

cache = SearchCache(ttl=600)  # 10 minute cache
router = SemanticRouter(indexer, cache=cache)
```

### Custom Weights

```python
from omni.core.router.hybrid_search import HybridSearch

# Adjust weights for more keyword-focused search
search = HybridSearch(indexer, keyword_indexer, semantic_weight=0.4, keyword_weight=0.6)
search.set_weights(0.5, 0.5)  # Equal weights
```

## API Reference

### SearchCache

| Method                | Description             |
| --------------------- | ----------------------- |
| `get(query)`          | Retrieve cached results |
| `set(query, results)` | Cache search results    |
| `clear()`             | Clear all entries       |
| `stats()`             | Get cache statistics    |
| `remove_expired()`    | Remove expired entries  |

### HybridSearch

| Method                            | Description            |
| --------------------------------- | ---------------------- |
| `search(query, limit, min_score)` | Execute hybrid search  |
| `set_weights(semantic, keyword)`  | Adjust scoring weights |
| `get_weights()`                   | Get current weights    |
| `stats()`                         | Get search statistics  |

### KeywordIndexer

| Method                             | Description      |
| ---------------------------------- | ---------------- |
| `index(doc_id, content, metadata)` | Index a document |
| `search(query, limit)`             | Keyword search   |
| `clear()`                          | Clear index      |

## Best Practices

1. **Cache TTL**: Set appropriate TTL based on how often skills are updated
2. **Cache Size**: Adjust `max_size` based on memory constraints
3. **Weight Tuning**: Adjust semantic/keyword weights based on your use case
4. **Warmup**: Pre-warm cache for common queries on startup

## Performance

| Operation       | Typical Latency |
| --------------- | --------------- |
| Cache hit       | < 1ms           |
| Semantic search | 10-50ms         |
| Hybrid search   | 15-60ms         |
| Cache miss      | 20-70ms         |
