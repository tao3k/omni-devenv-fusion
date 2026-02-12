# Knowledge Matrix

> Unified Knowledge Index for Context-Aware AI Agents
> **Status**: Active
> **Version**: v1.0 | 2026-01-14

## Overview

The Knowledge Matrix provides **Knowledge RAG** - a unified matrix for indexing and searching project documentation, specifications, and memory.

### Core Philosophy

| Component           | Purpose                       | Data Source                                    |
| ------------------- | ----------------------------- | ---------------------------------------------- |
| **Skills Table**    | Tool discovery and invocation | `assets/skills/*/scripts/*.py`                 |
| **Knowledge Table** | Documentation and specs       | `docs/`, `assets/knowledge/`, `assets/how-to/` |
| **Memory Table**    | Session and long-term memory  | [Hippocampus](hippocampus.md) (LanceDB)        |

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         The Knowledge Matrix         │
                    └─────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
   │   Skills    │          │  Knowledge  │          │   Memory    │
   │   Table     │          │   Table     │          │   Table     │
   └─────────────┘          └─────────────┘          └─────────────┘
   └─────────────────────────┴─────────────────────────┘
                    │                 │
                    ▼                 ▼
           ┌─────────────────┐ ┌─────────────────┐
           │ Tool Discovery  │ │  Doc Search     │
           │ (skill.search)  │ │  (knowledge.*)  │
           └─────────────────┘ └─────────────────┘
```

---

## 1. Type Definitions

**File**: `packages/python/agent/src/agent/core/types.py`

```python
from enum import Enum

class VectorTable(str, Enum):
    """Vector store table names."""
    SKILLS = "skills"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"

class ChunkStrategy(str, Enum):
    """Strategies for chunking documents."""
    FILE = "file"       # Whole file as one chunk
    SECTION = "section"  # Split by headers (##)
    PARAGRAPH = "paragraph"  # Split by paragraphs
```

---

## 2. Knowledge Indexer

**File**: `packages/python/agent/src/agent/core/knowledge/indexer.py`

### Core Components

```python
@dataclass
class DocRecord:
    """A scanned Markdown document."""
    id: str                      # file_path relative to root
    file_path: str               # Full path
    content: str                 # Full content (with frontmatter)
    body: str                    # Just the body (without frontmatter)
    file_hash: str               # SHA256 of content
    metadata: Dict[str, Any]     # Frontmatter metadata
    title: str = ""              # Extracted title

@dataclass
class DocChunk:
    """A chunk of a document for indexing."""
    id: str                      # e.g., "docs/api.md#chunk-0"
    doc_id: str                  # Parent document ID
    content: str                 # Chunk text content
    file_hash: str               # Parent document hash
    metadata: Dict[str, Any]     # Inherited from document
```

### Key Functions

```python
def scan_markdown_files(root_dir: str) -> List[DocRecord]:
    """
    Scan directory for Markdown files.
    - Extracts frontmatter metadata
    - Computes SHA256 hash for incremental updates
    - Skips .git, node_modules, __pycache__
    """

def extract_markdown_schema(record: DocRecord, strategy: str = "section") -> List[Dict]:
    """
    Convert DocRecord into vector store records (chunks).

    Strategies:
    - FILE: Single chunk for entire document
    - SECTION: Split by Markdown headers (##)
    - PARAGRAPH: Split by paragraphs
    """

async def sync_knowledge(store: Any, docs_dir: str, table_name: str = "knowledge") -> Dict:
    """
    Incrementally sync knowledge documents.
    - Compares file hashes with DB state
    - Only updates changed documents
    Returns: {"added": N, "updated": N, "deleted": N, "total": N}
    """
```

### Chunking Strategy

```
Input: docs/workflow.md

## 1. Git Workflow
Content about git...

## 2. Commit Process
Content about commits...

## 3. Code Review
Content about reviews...

Output Chunks:
├── docs/workflow.md#chunk-0: "## 1. Git Workflow\nContent..."
├── docs/workflow.md#chunk-1: "## 2. Commit Process\nContent..."
└── docs/workflow.md#chunk-2: "## 3. Code Review\nContent..."
```

---

## 3. VectorStore Integration

**File**: `packages/python/agent/src/agent/core/vector_store.py`

### New Method: search_knowledge_hybrid

```python
async def search_knowledge_hybrid(
    self,
    query: str,
    keywords: list[str] | None = None,
    limit: int = 5,
    table_name: str = "knowledge",
) -> list[dict[str, Any]]:
    """
    Search project knowledge using hybrid search (vector + keywords).

    Args:
        query: Natural language query
        keywords: Optional keywords to boost relevance
        limit: Maximum results (default: 5)
        table_name: Table to search (default: "knowledge")

    Returns:
        List of knowledge chunks with:
        - id: Chunk ID
        - content: Full chunk text
        - preview: Truncated preview
        - distance: Similarity score (lower = better)
        - metadata: doc_path, title, section, etc.
    """
```

---

## 4. Agent Tool: search_project_knowledge

**File**: `assets/skills/knowledge/scripts/search_docs.py`

```python
@skill_command(
    name="search_project_knowledge",
    description="[Knowledge RAG] Search project documentation, specs, and guides...",
    category="knowledge",
)
async def search_project_knowledge(
    query: str,
    limit: int = 5,
    keywords: list[str] | None = None,
) -> str:
    """
    Search the project knowledge base.

    Usage:
        @omni("knowledge.search_project_knowledge", {
            "query": "git commit 规范",
            "limit": 3
        })
    """
```

---

## 5. Usage Examples

### Direct Python API

```python
from agent.core.vector_store import get_vector_memory

vm = get_vector_memory()

# Semantic + keyword search
results = await vm.search_knowledge_hybrid(
    query="git workflow and commit process",
    keywords=["git", "commit", "workflow"],
    limit=5
)

for r in results:
    print(f"[{r['score']:.1%}] {r['title']} / {r['section']}")
    print(f"  {r['preview'][:100]}...")
```

### Agent Tool Usage

```
User: "What is our git commit convention?"

Agent:
  @omni("knowledge.search_project_knowledge", {
    "query": "git commit convention",
    "keywords": ["git", "commit", "convention"]
  })

Result:
  [
    {
      "title": "Git Workflow Guide",
      "section": "Commit Process",
      "content": "## Commit Process\nAll commits must use git_commit tool...",
      "score": 0.95
    }
  ]
```

---

## 6. Directory Structure

```
packages/python/agent/src/agent/core/
├── types.py                    # VectorTable enum
├── vector_store.py             # search_knowledge_hybrid()
└── knowledge/
    └── indexer.py              # scan_markdown_files, sync_knowledge

assets/skills/knowledge/scripts/
├── context.py                  # get_development_context
└── search_docs.py              # search_project_knowledge (NEW)
```

---

## 7. Configuration

**File**: merged `settings.yaml` runtime view
Base defaults come from `assets/settings.yaml`, and user/project overrides come from
`$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` (set via `--conf` or environment).

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
```

---

## 8. Testing

```bash
# Scan and display document stats
python3 -c "
from agent.core.knowledge.indexer import scan_markdown_files
records = scan_markdown_files('assets/how-to/')
print(f'Found {len(records)} docs')
"

# Test search
python3 -c "
import asyncio
from agent.core.vector_store import get_vector_memory

async def test():
    vm = get_vector_memory()
    results = await vm.search_knowledge_hybrid('git commit', limit=3)
    print(f'Found {len(results)} results')

asyncio.run(test())
"
```

---

## 9. Comparison: Skills vs Knowledge

| Aspect           | Skills (Tool Discovery)      | Knowledge (Docs Search)            |
| ---------------- | ---------------------------- | ---------------------------------- |
| **Target**       | Tool discovery               | Documentation search               |
| **Source**       | Python scripts (\*.py)       | Markdown files (\*.md)             |
| **Unit**         | Function                     | Section/Paragraph                  |
| **Index Key**    | tool_name (e.g., git.commit) | doc_id#chunk-N                     |
| **Primary Tool** | skill.search_tools           | knowledge.search_project_knowledge |
| **Core Tool**    | skill.search_tools           | knowledge.get_development_context  |

---

## 10. Future Enhancements

- [ ] Auto-sync on file changes (Watcher integration)
- [ ] Memory table for session persistence
- [ ] Cross-reference linking between docs
- [ ] Image/diagram extraction and indexing
- [ ] Multi-language support (English/Chinese)

---

## Related Documentation

- [Hippocampus](hippocampus.md) - Memory Interface (long-term memory for self-learning)
- [Memory Mesh](memory-mesh.md) - Episodic memory detailed architecture
- [Omni Loop](omni-loop.md) - CCA Runtime with Knowledge + Memory
