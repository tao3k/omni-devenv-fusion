# Librarian

> RAG-powered Knowledge Retrieval Interface for Context-Aware AI Agents

## Overview

Librarian is the **retrieval interface** layer of the Knowledge Matrix, providing semantic search capabilities over project documentation, specifications, and harvested experiences. It bridges the gap between raw vector storage and high-level agent reasoning.

## The Librarian's Exam: Real-World Scenarios

Librarian is validated through 6 key scenarios representing common user needs:

### Scenario 1: "The Architect" - Semantic Search

**Goal**: Understand concepts, not just keywords.

```
User Query: "How is the system structured?"
              ↓
Librarian searches for conceptual matches
              ↓
Returns: "The Trinity Architecture divides the system into Foundation, Core, and Agent layers."
```

**Test Case**: Semantic search should understand 'system structure' even when querying with different words.

### Scenario 2: "The Debugger" - Keyword Search

**Goal**: Find exact error codes and messages.

```
User Query: "ERROR_503"
              ↓
Librarian searches for exact matches
              ↓
Returns: "ERROR_503: Service Unavailable - Retry after backoff."
```

**Test Case**: Search for ERROR_503 should find the service unavailable message.

### Scenario 3: "The Developer" - Code Search

**Goal**: Retrieve function definitions and code patterns.

```
User Query: "connect_to_db"
              ↓
Librarian searches code chunks
              ↓
Returns: "def connect_to_db(timeout: int) -> bool: Establishes connection to the database."
```

**Test Case**: Search for function name should find its definition with context.

### Scenario 4: "The Updater" - Incremental Updates

**Goal**: Document changes reflect in search immediately.

```
Step 1: Ingest "Status: GREEN - All systems operational."
Step 2: Search for "Status" → Returns GREEN
Step 3: Modify file to "Status: RED - Critical Failure!"
Step 4: Re-ingest file
Step 5: Search for "Status" → Returns RED
```

**Test Case**: Updated content should immediately reflect in search results.

### Scenario 5: "The Hybrid Search" - Combined Search

**Goal**: Both semantic and keyword queries work seamlessly.

```
Semantic Query: "database connection"
              ↓
Returns function definition with docstring

Keyword Query: "ERROR_500"
              ↓
Returns exact error code entry
```

**Test Case**: Both semantic and keyword queries return relevant results.

### Scenario 6: "Edge Cases" - Robustness

**Goal**: Handle errors gracefully.

```
Edge Cases Tested:
├── Empty knowledge base → Returns empty results
├── Nonexistent file → Returns (False, 0)
├── Empty file → Returns success with 1+ chunks
├── Low relevance score → Filtered by threshold
└── Search error → Returns empty, logs warning
```

**Test Case**: All edge cases handled without crashes.

## Position in Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Knowledge Lifecycle                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. INGEST (Knowledge Indexer)                                              │
│     docs/*.md → scan_markdown_files() → DocChunk → VectorStore              │
│                                                                             │
│  2. STORE (Knowledge Matrix)                                                │
│     ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                    │
│     │   Skills    │   │  Knowledge  │   │   Memory    │                    │
│     │   Table     │   │   Table     │   │   Table     │                    │
│     └─────────────┘   └─────────────┘   └─────────────┘                    │
│                              │                                              │
│  3. RETRIEVE (Librarian) ◄───┘                                              │
│     consult_knowledge_base() ──► Semantic Search ──► Formatted Results      │
│                                                                             │
│  4. APPLY (Agent/Router)                                                    │
│     Agent receives context ──► Informed Decision Making                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Knowledge Lifecycle

### 1. Ingestion

The Knowledge Indexer scans Markdown files and creates searchable chunks:

```python
from agent.core.knowledge.indexer import scan_markdown_files, sync_knowledge

# Scan docs directory
records = scan_markdown_files("docs/")

# Sync with incremental updates (only changed files)
stats = await sync_knowledge(store, "docs/", table_name="knowledge")
# Returns: {"added": 5, "updated": 2, "deleted": 1, "total": 42}
```

### 2. Storage (Knowledge Matrix)

Three tables work together:

| Table         | Purpose         | Data Source                                    |
| ------------- | --------------- | ---------------------------------------------- |
| **Skills**    | Tool discovery  | `assets/skills/*/scripts/*.py`                 |
| **Knowledge** | Documentation   | `docs/`, `assets/knowledge/`, `assets/how-to/` |
| **Memory**    | Session history | Runtime interactions                           |

### 3. Retrieval (Librarian)

Librarian provides the retrieval interface:

```python
from agent.capabilities.knowledge.librarian import consult_knowledge_base

result = await consult_knowledge_base(
    query="git commit workflow",
    n_results=5,
    domain_filter="git"
)
```

### 4. Application

Agents and Routers use retrieved knowledge for informed decision-making.

## Core Functions

### consult_knowledge_base

Primary semantic search interface.

```python
async def consult_knowledge_base(
    query: str,
    n_results: int = 5,
    collection: str | None = None,
    domain_filter: str | None = None,
) -> Dict[str, Any]:
    """
    Query the project knowledge base using semantic search.

    Args:
        query: Search query (what you're looking for)
        n_results: Number of results to return (default: 5)
        collection: Optional collection name
        domain_filter: Domain tag filter (e.g., "git", "architecture")

    Returns:
        {
            "success": True,
            "query": "git commit workflow",
            "results": [
                {
                    "id": "docs/git.md#chunk-2",
                    "content": "Always run git status before...",
                    "metadata": {"domain": "git", "priority": "high"},
                    "relevance_score": 0.92
                }
            ],
            "count": 5
        }
    """
```

### ingest_knowledge

Add new documents to the knowledge base.

```python
async def ingest_knowledge(
    documents: List[str],
    ids: List[str],
    collection: str | None = None,
    domains: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Add new knowledge to the vector store.

    Use this to teach the system about:
    - Project-specific workflows
    - Architectural decisions
    - Code patterns and examples
    """
```

### bootstrap_knowledge

Initialize knowledge base with core documentation.

```python
async def bootstrap_knowledge() -> str:
    """
    Bootstrap with essential project documentation.
    Called once on first setup.

    Returns:
        "✅ Knowledge base bootstrapped successfully..."
    """
```

### search_project_rules

Search for high-priority rules and workflows.

```python
async def search_project_rules(query: str) -> str:
    """
    Convenience wrapper that filters for priority: high/medium.
    """
```

### get_skill_lessons

Retrieve skill-specific lessons from harvested experiences.

```python
async def get_skill_lessons(
    skills: List[str],
    limit: int = 5
) -> str:
    """
    [Experiential Agent] Retrieve lessons tagged for specific skills.

    Searches harvested insights for past mistakes, pitfalls,
    and best practices relevant to the given skills.
    """
```

## Integration with Knowledge Matrix

### Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Knowledge Matrix Integration                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Knowledge Indexer                                                           │
│  (Ingestion Layer)                                                           │
│       │                                                                     │
│       │ scan_markdown_files()                                               │
│       │ extract_markdown_schema()                                           │
│       │ sync_knowledge()                                                    │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VectorStore (Storage Layer)                       │   │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │   │
│  │   │   Skills    │   │  Knowledge  │   │   Memory    │               │   │
│  │   └─────────────┘   └─────────────┘   └─────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                        │                                            │
│       │                        │ search_knowledge_hybrid()                  │
│       │                        ▼                                            │
│       │                  ┌─────────────────────┐                           │
│       │                  │     Librarian       │ ◄── Retrieval Interface   │
│       │                  │ (Semantic Search)   │                           │
│       │                  └──────────┬──────────┘                           │
│       │                             │                                       │
│       ▼                             ▼                                       │
│  skill.search_tools         knowledge.search_project_knowledge              │
│  skill.discover             consult_knowledge_base()                        │
│                             get_skill_lessons()                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Chunking Strategy

Knowledge Matrix uses section-based chunking:

```
Input: docs/workflow.md

## 1. Git Workflow
Content about git...

## 2. Commit Process
Content about commits...

Output Chunks:
├── docs/workflow.md#chunk-0: "## 1. Git Workflow\nContent..."
├── docs/workflow.md#chunk-1: "## 2. Commit Process\nContent..."
```

Librarian queries these chunks via semantic similarity.

## Agent Integration

### Wisdom-Aware Routing

Router consults Librarian during mission brief generation:

```
User Query: "commit my changes"
     ↓
SemanticRouter.route()
     ↓
┌─────────────────────────────────────────────────────┐
│  Three-Way Parallel:                                │
│  1. Build routing menu (blocking, ~5ms)             │
│  2. Consult Librarian for wisdom (parallel, ~50ms)  │ ← Librarian
│  3. ContextSniffer.get_snapshot() (parallel, ~10ms) │
└─────────────────────────────────────────────────────┘
     ↓
LLM generates Mission Brief with retrieved lessons
```

### Experiential Agent

Agents retrieve skill-specific lessons before execution:

```python
# In BaseAgent._get_agent_skill_lessons()
lessons = await get_skill_lessons(skills=["git", "omnicell"])

# Injected into system prompt:
"""
### 🛑 KNOWN PITFALLS & PAST LESSONS

⭐⭐⭐⭐ **git**: Don't run git commit without staging files first
⭐⭐⭐ **omnicell**: Uses Nushell for all file operations, returns structured JSON
"""
```

### Holographic Agent

Combined with ContextSniffer for real-time awareness:

```
Agent ReAct Loop
     ↓
┌─────────────────────────────────────────────────────┐
│  Before each step:                                  │
│  1. Get live environment snapshot (Holographic)     │
│  2. Get relevant skill lessons (Experiential)       │ ← Librarian
│  3. Execute with full context                       │
└─────────────────────────────────────────────────────┘
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         End-to-End Data Flow                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SOURCE DOCUMENTS                                                            │
│  ├── docs/*.md                     (project documentation)                  │
│  ├── assets/specs/*.md             (feature specifications)                 │
│  ├── assets/how-to/*.md            (guides and tutorials)                   │
│  └── assets/knowledge/harvested/*.md (learned experiences)                  │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────┐                                                        │
│  │  Knowledge      │  scan_markdown_files()                                 │
│  │  Indexer        │  extract_markdown_schema(strategy="section")           │
│  └────────┬────────┘                                                        │
│           │ DocChunk(id, content, metadata, file_hash)                      │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  VectorStore    │  Embedding generation + LanceDB                           │
│  │  (Knowledge     │  Incremental sync (hash-based dedup)                     │
│  │   Table)        │  Rust-accelerated via omni-vector                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  Librarian      │  Semantic search + keyword boosting                    │
│  │  (Retrieval)    │  Domain filtering + relevance scoring                  │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  Agent/Router   │  Context-aware decision making                         │
│  │  (Consumer)     │  Wisdom-aware mission briefs                           │
│  └─────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration

### settings.yaml

```yaml
knowledge:
  # Directories to index
  directories:
    - "docs/"
    - "assets/knowledge/"
    - "assets/how-to/"
    - "assets/specs/"

  # Chunking strategy: "file", "section", "paragraph"
  chunk_strategy: "section"

  # Minimum chunk size (characters)
  min_chunk_size: 50

vector_store:
  provider: "lancedb" # Rust-accelerated via omni-vector
  persist_directory: ".cache/omni-vector"
```

## Performance Characteristics

| Operation          | Time       | Notes                         |
| ------------------ | ---------- | ----------------------------- |
| Semantic search    | ~50ms      | Vector similarity + reranking |
| Document ingestion | ~100ms/doc | Includes embedding generation |
| Bootstrap (full)   | ~5s        | Initial scan and index        |
| Incremental sync   | ~10ms      | Hash-based change detection   |

## File Structure

```
packages/python/agent/src/agent/
├── capabilities/knowledge/
│   ├── __init__.py
│   └── librarian.py              # Librarian interface (this doc)
├── core/
│   ├── vector_store/             # VectorStore abstraction
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── index.py
│   └── knowledge/
│       └── indexer.py            # Knowledge Indexer
└── core/router/
    └── semantic_router.py        # Wisdom-Aware Routing integration

assets/skills/knowledge/scripts/
├── context.py                    # get_development_context
└── search_docs.py                # search_project_knowledge
```

## Related Documentation

- [Knowledge Matrix](../human/architecture/knowledge-matrix.md) - Unified knowledge index architecture
- [Trinity Architecture](../explanation/trinity-architecture.md) - Overall system design
- [Memory Mesh](../human/architecture/memory-mesh.md) - Episodic memory for self-learning
