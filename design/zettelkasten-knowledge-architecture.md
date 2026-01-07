# Zettelkasten-Based Knowledge Architecture

> Discussion document - not a final decision
> Status: Open for debate
> Date: 2026-01-07

---

## Context

Current architecture uses vector database (FAISS) for semantic search. Maintenance burden is high:

- Index rebuilds on content changes
- Embedding model drift
- Database migration complexity

Alternative: Zettelkasten methodology using Rucola + Repomix Cache.

---

## Architecture

```
                        LLM Agent
                            │
                            │ "What do I know about X?"
                            │ "Research latest AI trends"
                            ▼
               ┌─────────────────────────────┐
               │      Omni MCP Server        │
               │  ┌───────────────────────┐  │
               │  │ knowledge.create()    │  │
               │  │ knowledge.suggest()   │  │
               │  │ knowledge.query()     │  │ ← Local knowledge
               │  │ knowledge.research()  │  │ ← External knowledge
               │  └───────────────────────┘  │
               └─────────────┬───────────────┘
                             │
                             ▼
               ┌─────────────────────────────┐
               │    Knowledge Layer          │
               │  ┌───────────────────────┐  │
               │  │ Rucola CLI Wrapper    │  │ ← Local knowledge
               │  │ Repomix Cache         │  │ ← XML format
               │  │ External Knowledge    │  │ ← ChromaDB (crawled)
               │  └───────────────────────┘  │
               └─────────────┬───────────────┘
                             │
       ┌─────────────────────┴─────────────────────┐
       │                                             │
       ▼                                             ▼
┌──────────────────┐                    ┌────────────────────────┐
│ Rucola CLI       │ ← Zettelkasten     │ External Knowledge     │
│ • search         │ ← Local knowledge  │ ChromaDB + Metadata    │
│ • graph          │                    │ • Crawled web pages    │
│ • backlinks      │                    │ • Research papers      │
└──────────────────┘                    │ • Updated content      │
                                        └────────────────────────┘
```

---

## Separation of Concerns

| Layer             | Type               | Technology   | Purpose                                    | Required?   |
| ----------------- | ------------------ | ------------ | ------------------------------------------ | ----------- |
| **Zettelkasten**  | Local Knowledge    | Rucola       | Project rules, architecture, skill prompts | Optional    |
| **ChromaDB**      | External Knowledge | Vector Store | Crawled content, research materials, docs  | Required    |
| **Repomix Cache** | LLM Interface      | XML Format   | Aggregate → Token optimize → Cache         | Recommended |

---

## Why Two Systems?

| Aspect    | Local (Zettelkasten) | External (ChromaDB)        |
| --------- | -------------------- | -------------------------- |
| Content   | Markdown files       | Crawled web pages, PDFs    |
| Updates   | Manual edit          | Auto-detect (content hash) |
| Structure | Wiki-links           | Flat storage with metadata |
| Purpose   | Project knowledge    | Research & reference       |

**Key Insight**:

- **Zettelkasten**: Human-authored, structured, linked knowledge
- **ChromaDB**: Machine-crawled, unstructured, searchable reference

---

## Local Knowledge: Zettelkasten (Rucola)

**Input**: User-created markdown notes
**Output**: Structured knowledge with wiki-links

**Capabilities**:

- CRUD operations on notes
- Full-text search
- Graph traversal (backlinks, forward links)
- Note statistics

**Responsibility**:

- Project rules and workflows
- Architecture decisions
- Skill prompts and documentation

---

## External Knowledge: ChromaDB

**Input**: Crawled content from crawl4ai, GitHub repos, PDFs, APIs
**Output**: Searchable vector store with metadata

**Capabilities**:

- Semantic search over crawled content
- Content hash for change detection
- Source URL + date metadata
- Full content storage (not just chunks)
- Flexible extraction: Full or Compressed

**Workflow**:

```
Source: GitHub Repo, Web Page, PDF, API Doc
    │
    ▼
┌─────────────────┐     ┌─────────────────────┐
│ Repomix (Full)  │────▶│   ChromaDB          │  ← Store complete content
│ Complete Mix    │     │   (Vector Store)    │
└─────────────────┘     │   - Full content    │
                        │   - Semantic index  │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Query Strategy    │
                        ├─────────────────────┤
                        │ 1. Semantic Search  │
                        │ 2. Get from ChromaDB│
                        │ 3. Decision:        │
                        │    • Full → LLM     │  ← Research mode
                        │    • Compress → LLM │  ← Quick mode
                        └─────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │        LLM          │
                        └─────────────────────┘
```

**Key Design**:

- **ChromaDB = Source of Truth** - Stores complete content
- **Flexible Output** - LLM/user decides: Full or Compressed
- **Repomix Optional** - Can compress before storing or after retrieval

---

## Repomix Cache Boundaries

```
Input: Notes from Rucola OR results from ChromaDB
   │
   ▼
┌─────────────────────────────┐
│  1. Aggregate               │  Gather related content
│  2. XML Format              │  Convert to LLM-readable XML
│  3. Token Optimization      │  Truncate by token limit
│  4. Cache                   │  Store for faster retrieval
└─────────────────────────────┘
   │
   ▼
Output: XML context for LLM
```

---

## MCP Tool Definitions

```python
@tool
def knowledge_create(
    title: str,
    content: str,
    tags: list[str] = [],
    related_notes: list[str] = [],
    category: str = "inbox",
) -> str:
    """
    Create a local note with Zettelkasten structure.
    Frontmatter, tags, [[wiki-links]] automatically added.
    """
    ...

@tool
def knowledge_suggest(
    content: str,
    limit: int = 5,
) -> list[str]:
    """
    Suggest related local notes based on content.
    Uses Rucola search internally.
    """
    ...

@tool
def knowledge_query(
    query: str,
    max_tokens: int = 8000,
    source: str = "local",  # "local", "external", or "both"
    compression: str = "auto",  # "none", "auto", "minimal"
) -> str:
    """
    Query knowledge and return LLM-readable XML context.

    Flow (local):
    1. Rucola search → Get related notes
    2. Repomix cache → Aggregate + XML format + Token optimize
    3. Return cached XML context

    Flow (external):
    1. ChromaDB semantic search → Get crawled content
    2. Decision: Full or Compressed?
       - "none" → Return full content
       - "auto" → LLM decides based on token limit
       - "minimal" → Aggressive compression
    3. Return context for LLM
    """
    ...

@tool
def knowledge_research(
    query: str,
    urls: list[str] = [],
    sync_to_local: bool = False,
) -> str:
    """
    Research external knowledge.

    1. Crawl specified URLs (via crawl4ai)
    2. Store in ChromaDB with metadata
    3. Detect if content changed (hash comparison)
    4. Optionally sync to Zettelkasten (external → local)
    5. Return XML context for LLM
    """
    ...
```

---

## External Knowledge Workflow

```
┌─────────────────────────────────────────────────────────┐
│                 External Knowledge Manager              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  URLs/Crawl Config                                       │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────┐     ┌──────────┐     ┌─────────────────┐  │
│  │ crawl4ai│────▶│  Cache   │────▶│  Hash Check     │  │
│  │  Crawl  │     │  (disk)  │     │  (detect delta) │  │
│  └─────────┘     └──────────┘     └────────┬────────┘  │
│       │                                    │           │
│       │                              ┌─────┴─────┐     │
│       │                              │ New only  │     │
│       │                              │ Skip dup  │     │
│       │                              └─────┬─────┘     │
│       │                                    │           │
│       ▼                                    ▼           │
│  ┌─────────┐                        ┌─────────────┐    │
│  │ChromaDB │◀───────────────────────│   Update    │    │
│  │ Storage │                        │   Metadata  │    │
│  └─────────┘                        └─────────────┘    │
│       │                                                  │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────────────────────────────────┐           │
│  │  XML Context for LLM                    │           │
│  └─────────────────────────────────────────┘           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Vault Structure

```
assets/knowledge/
├── local/              # Zettelkasten (Rucola)
│   ├── inbox/         # Temporary notes
│   ├── projects/      # Project-related
│   ├── reference/     # Reference materials
│   └── archive/       # Archived
└── external/          # ChromaDB metadata (optional)
    └── .cache/        # Crawled content cache
```

---

## Questions to Resolve

1. **External Sync Strategy**:
   - Place external content in Rucola-managed folder → auto-sync
   - No separate sync mechanism needed
   - Rucola handles folder watching and graph updates

2. **Caching**:
   - TTL (Time To Live) not applicable
   - External content rarely re-crawled
   - On-demand fetch with hash-based change detection

3. **Deduplication**:
   - Rare case: same content from different URLs
   - LLM can handle duplicates (minor token cost)
   - No complex dedupe logic needed

**Philosophy**: Don't over-engineer. Let LLM handle edge cases.

---

## Pros

- **External Knowledge**: ChromaDB enables semantic search over crawled content
- **Local Knowledge**: Zettelkasten provides structured, linked notes
- **Efficiency**: Avoid duplicate crawling with hash-based detection
- **LLM Interface**: XML context is LLM-friendly
- **Simplicity**: Rucola handles sync, no extra bridge needed
- **Pragmatism**: Let LLM handle edge cases, no over-engineering

## Cons

- **Two Systems**: ChromaDB (external) + Rucola (local)
- **Crawl Maintenance**: crawl4ai dependencies
- **Optional Local**: Can skip Zettelkasten if all knowledge is external

---

## Related Reading

- [Rucola](https://github.com/Linus-Mussmaecher/rucola) - Terminal-based Zettelkasten
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [crawl4ai](https://github.com/unclecode/crawl4ai) - Web crawling
- [Zettelkasten Method](https://zettelkasten.de/)
- [Repomix](https://github.com/yl439/repomix)

---

## Next Steps

- [ ] Install and test Rucola CLI
- [ ] Define MCP tool signatures
- [ ] Prototype Rucola CLI wrapper (knowledge.create, knowledge.query)
- [ ] Design External Knowledge workflow (crawl4ai → ChromaDB)
- [ ] Implement Repomix Cache XML schema
- [ ] Test crawl4ai → ChromaDB integration
