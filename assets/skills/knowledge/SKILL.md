---
name: knowledge
description: Use when searching documentation, retrieving project standards, capturing durable notes, and managing long-term knowledge base content.
metadata:
  author: omni-dev-fusion
  version: "1.1.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/knowledge"
  routing_keywords:
    - "knowledge"
    - "context"
    - "rules"
    - "standards"
    - "link graph"
    - "wendao"
    - "bidirectional links"
    - "reasoning search"
    - "documentation"
    - "how to"
    - "explain"
    - "what is"
    - "guidelines"
    - "project rules"
    - "conventions"
    - "workflow"
    - "note"
    - "remember"
    - "summary"
    - "learn"
    - "capture"
  intents:
    - "Consult project rules"
    - "Look up coding standards"
    - "Check architecture decisions"
    - "Review workflow guidelines"
    - "Take notes during session"
    - "Summarize conversation"
    - "Save important information"
    - "Recall knowledge from notes"
---

# Knowledge Skill

Project Cortex - Structural Knowledge Injection and Long-Term Knowledge Retrieval.

Boundary note:

- This skill is for durable/reusable knowledge.
- Short-term operational memory belongs to Rust memory core and is exposed separately via memory skill facade.

## Commands

### Unified Search (primary)

**Single entry point for all knowledge search.** Use this instead of separate search/link_graph_hybrid_search to avoid tool ambiguity.

| Parameter     | Type | Default    | Description                                                                                            |
| ------------- | ---- | ---------- | ------------------------------------------------------------------------------------------------------ |
| `query`       | str  | -          | Search query (required)                                                                                |
| `mode`        | str  | `"hybrid"` | `hybrid` (link_graph+vector), `keyword` (ripgrep), `link_graph` (links only), `vector` (semantic only) |
| `max_results` | int  | 10         | Maximum results                                                                                        |
| `scope`       | str  | `"all"`    | For mode=keyword only: docs, references, skills, harvested, all                                        |

**Example:**

```python
@omni("knowledge.search", {"query": "UltraRAG research report"})
@omni("knowledge.search", {"query": "architecture", "mode": "keyword", "scope": "harvested"})
```

### Documentation Commands

#### `search_documentation`

Search markdown documentation and references for specific topics.

| Parameter | Type | Default | Description            |
| --------- | ---- | ------- | ---------------------- |
| `query`   | str  | -       | Search term (required) |

**Example:**

```python
@omni("knowledge.search_documentation", {"query": "trinity architecture"})
```

#### `search_standards`

Search coding standards and engineering guidelines in docs/reference/.

| Parameter | Type | Default | Description                  |
| --------- | ---- | ------- | ---------------------------- |
| `topic`   | str  | -       | Engineering topic (required) |

**Example:**

```python
@omni("knowledge.search_standards", {"topic": "python linting"})
```

### Semantic Search Commands

#### `knowledge_search` (alias: `code_search`)

Semantic search for code patterns and documentation in knowledge base.

| Parameter | Type | Default | Description                       |
| --------- | ---- | ------- | --------------------------------- |
| `query`   | str  | -       | Natural language query (required) |
| `limit`   | int  | 5       | Maximum results                   |

**Example:**

```python
@omni("knowledge.knowledge_search", {"query": "error handling patterns", "limit": 5})
```

#### `code_context`

Get LLM-ready context blocks for a query.

| Parameter | Type | Default | Description                  |
| --------- | ---- | ------- | ---------------------------- |
| `query`   | str  | -       | Query for context (required) |
| `limit`   | int  | 3       | Number of context blocks     |

**Example:**

```python
@omni("knowledge.code_context", {"query": "how to handle errors", "limit": 3})
```

### Knowledge Base Commands

#### `update_knowledge_base`

Save knowledge entry for future retrieval.

| Parameter  | Type      | Default | Description                                           |
| ---------- | --------- | ------- | ----------------------------------------------------- |
| `category` | str       | -       | patterns/solutions/errors/techniques/notes (required) |
| `title`    | str       | -       | Entry title (required)                                |
| `content`  | str       | -       | Markdown content (required)                           |
| `tags`     | list[str] | []      | Tags for categorization                               |

**Example:**

```python
@omni("knowledge.update_knowledge_base", {
    "category": "patterns",
    "title": "Error Handling Pattern",
    "content": "Use Result types instead of exceptions...",
    "tags": ["error", "python"]
})
```

#### `search_notes`

Search existing notes and knowledge entries.

| Parameter  | Type | Default | Description             |
| ---------- | ---- | ------- | ----------------------- |
| `query`    | str  | -       | Search query (required) |
| `category` | str  | None    | Filter by category      |
| `limit`    | int  | 10      | Maximum results         |

**Example:**

```python
@omni("knowledge.search_notes", {"query": "error handling", "category": "patterns"})
```

#### `summarize_session`

Summarize current session trajectory into structured markdown.

| Parameter          | Type       | Default | Description                          |
| ------------------ | ---------- | ------- | ------------------------------------ |
| `session_id`       | str        | -       | Unique session identifier (required) |
| `trajectory`       | list[dict] | -       | Execution steps (required)           |
| `include_failures` | bool       | true    | Include failed approaches            |

**Example:**

```python
@omni("knowledge.summarize_session", {
    "session_id": "session-123",
    "trajectory": [{"step": 1, "action": "search", "result": "found 5 files"}],
    "include_failures": true
})
```

### Knowledge Ops Commands

#### `ingest_knowledge`

Ingest or update project knowledge base.

| Parameter | Type | Default | Description           |
| --------- | ---- | ------- | --------------------- |
| `clean`   | bool | false   | Full re-index if true |

**Example:**

```python
@omni("knowledge.ingest_knowledge", {"clean": false})
```

#### `knowledge_status`

Check knowledge base status.

**Example:**

```python
@omni("knowledge.knowledge_status")
```

### Link Graph and TOC (use unified `search` for link_graph-only)

For link-graph-only (link reasoning, no vector), use the unified search with `mode="link_graph"`:

```python
@omni("knowledge.search", {"query": "agent skills progressive disclosure", "mode": "link_graph", "max_results": 5})
```

For structured filtering/sorting, use schema-v2 `search_options`:

```python
@omni("knowledge.search", {
  "query": "architecture",
  "mode": "link_graph",
  "max_results": 5,
  "search_options": {
    "schema": "omni.link_graph.search_options.v2",
    "match_strategy": "exact",
    "sort_terms": [{"field": "title", "order": "asc"}],
    "filters": {
      "link_to": {"seeds": ["design-doc"], "recursive": true, "max_distance": 2},
      "tags": {"any": ["architecture", "design"]}
    }
  }
})
```

`mode="link_graph"` responses include `parsed_query` (residual free-text after directive extraction) and normalized effective `search_options` from the Rust planner.

#### `link_graph_toc`

Get Table of Contents for LLM context (all notes overview).

| Parameter | Type | Default | Description             |
| --------- | ---- | ------- | ----------------------- |
| `limit`   | int  | 100     | Maximum notes to return |

**Example:**

```python
@omni("knowledge.link_graph_toc", {"limit": 50})
```

#### `link_graph_hybrid_search`

Hybrid search combining LinkGraph reasoning + vector search fallback.

| Parameter     | Type | Default | Description             |
| ------------- | ---- | ------- | ----------------------- |
| `query`       | str  | -       | Search query (required) |
| `max_results` | int  | 10      | Maximum results         |
| `use_hybrid`  | bool | true    | Use vector fallback     |

**Example:**

```python
@omni("knowledge.link_graph_hybrid_search", {"query": "architecture MCP", "use_hybrid": true})
```

#### `link_graph_stats`

Get knowledge base statistics.

**Example:**

```python
@omni("knowledge.link_graph_stats")
```

#### `link_graph_refresh_index`

Trigger LinkGraph index refresh through the common backend API.
Useful for operations/debugging with `-v` monitor output.

| Parameter       | Type      | Default | Description                              |
| --------------- | --------- | ------- | ---------------------------------------- |
| `changed_paths` | list[str] | []      | Changed paths for delta refresh planning |
| `force_full`    | bool      | false   | Force full rebuild instead of delta path |

**Example:**

```python
@omni("knowledge.link_graph_refresh_index", {"changed_paths": ["docs/architecture/kernel.md"]})
@omni("knowledge.link_graph_refresh_index", {"force_full": true})
```

#### `link_graph_links`

Find notes linked to/from a specific note.

| Parameter   | Type | Default | Description             |
| ----------- | ---- | ------- | ----------------------- |
| `note_id`   | str  | -       | Note ID (required)      |
| `direction` | str  | "both"  | "to", "from", or "both" |

**Example:**

```python
@omni("knowledge.link_graph_links", {"note_id": "architecture", "direction": "both"})
```

#### `link_graph_find_related`

Find notes related to a given note using link-graph traversal.

| Parameter      | Type | Default | Description                 |
| -------------- | ---- | ------- | --------------------------- |
| `note_id`      | str  | -       | Starting note ID (required) |
| `max_distance` | int  | 2       | Maximum link distance       |
| `limit`        | int  | 20      | Maximum results             |

**Example:**

```python
@omni("knowledge.link_graph_find_related", {"note_id": "agent-skills", "max_distance": 2})
```

## Core Concepts

| Topic                 | Description                       | Reference                           |
| --------------------- | --------------------------------- | ----------------------------------- |
| Development Context   | Project rules, scopes, guardrails | [context.md](references/context.md) |
| Writing Memory        | Writing style guidelines          | [writing.md](references/writing.md) |
| Session Summarization | Trajectory capture pattern        | [session.md](references/session.md) |

## Best Practices

- **Search first**: Before adding new knowledge, search for duplicates
- **Use categories**: Organize entries by category (patterns/solutions/errors/techniques)
- **Add tags**: Use consistent tags for better retrieval
- **Include examples**: Code examples improve AI understanding

#### `ingest_document`

Ingest a document (PDF, Markdown, etc.) with full RAG pipeline: parse, chunk, optional entity extraction and graph storage, then vector store.

| Parameter           | Type | Default      | Description                                                                |
| ------------------- | ---- | ------------ | -------------------------------------------------------------------------- |
| `file_path`         | str  | -            | Local path or PDF URL (e.g. `https://arxiv.org/pdf/2601.03192`) (required) |
| `chunking_strategy` | str  | `"semantic"` | sentence, paragraph, sliding_window, semantic                              |
| `extract_entities`  | bool | true         | Extract entities and store in knowledge graph                              |
| `store_in_graph`    | bool | true         | Store extracted entities/relations in graph                                |

When `file_path` is a URL, the file is downloaded to project data (`.data/knowledge/downloads`) then processed.

**Example:**

```python
@omni("knowledge.ingest_document", {"file_path": "docs/guide.pdf"})
@omni("knowledge.ingest_document", {"file_path": "https://arxiv.org/pdf/2601.03192"})
```

## Advanced

- **Semantic vs Text Search**: Use `knowledge_search` for semantic understanding, `search_documentation` for exact matches
- **Batch Ingest**: Call `ingest_knowledge` with `clean=false` for incremental updates
- **Session Continuity**: Use `session_id` to link related sessions
- **PDF from URL**: Use `ingest_document` with a PDF URL; file is saved under project data then ingested
