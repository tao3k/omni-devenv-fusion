---
name: knowledge
description: Use when searching documentation, retrieving project standards, managing persistent memory, capturing session notes, or querying the knowledge base.
metadata:
  author: omni-dev-fusion
  version: "1.1.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/knowledge"
  routing_keywords:
    - "knowledge"
    - "context"
    - "rules"
    - "standards"
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
    - "memory"
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

Project Cortex - Structural Knowledge Injection, Semantic Search & Persistent Memory.

## Commands

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

### Memory Commands

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

## Advanced

- **Semantic vs Text Search**: Use `knowledge_search` for semantic understanding, `search_documentation` for exact matches
- **Batch Ingest**: Call `ingest_knowledge` with `clean=false` for incremental updates
- **Session Continuity**: Use `session_id` to link related sessions
