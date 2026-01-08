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

Alternative: Zettelkasten methodology using mcp-obsidian + Rucola + ChromaDB.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge System                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LOCAL (Zettelkasten)                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  mcp-obsidian  ← Obsidian MCP (Full Obsidian Integ) │   │
│  │  • Create/Edit notes                                 │   │
│  │  • Wiki-links, backlinks                             │   │
│  │  • Graph traversal                                   │   │
│  │  • Search, tags                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↑                                  │
│                    Rucola (CLI Tool)                        │
│                    • Quick operations, stats                │
│                    • CLI management                         │
│                                                             │
│  EXTERNAL (ChromaDB)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  crawl4ai → ChromaDB → Semantic Search               │   │
│  │  • Repomix (Full) → Store                            │   │
│  │  • Compression option for LLM                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Role Division

| Tool             | Role                 | Responsibility                          |
| ---------------- | -------------------- | --------------------------------------- |
| **mcp-obsidian** | Obsidian Integration | Notes CRUD, wiki-links, graph, search   |
| **Rucola**       | CLI Helper           | Quick operations, stats, CLI management |
| **ChromaDB**     | External Knowledge   | Crawled content, semantic search        |

---

## Why mcp-obsidian?

[mcp-obsidian](https://github.com/bitbonsai/mcp-obsidian) provides:

- Full Obsidian vault integration
- Wiki-link support (bidirectional)
- Backlink management
- Graph traversal
- Tag-based search
- Note templates

**Rucola** remains useful as:

- Fast CLI operations
- Stats and overview
- Alternative to Obsidian when not available

---

## External Knowledge: ChromaDB

**Input**: Crawled content from crawl4ai, GitHub repos, PDFs, APIs
**Output**: Searchable vector store with metadata

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

---

## Separation of Concerns

| Layer             | Type               | Technology   | Purpose                            | Required?   |
| ----------------- | ------------------ | ------------ | ---------------------------------- | ----------- |
| **mcp-obsidian**  | Local Knowledge    | Obsidian MCP | Notes, links, graph                | Required    |
| **Rucola**        | Local Helper       | CLI Tool     | Quick operations                   | Optional    |
| **ChromaDB**      | External Knowledge | Vector Store | Crawled content, research          | Required    |
| **Repomix Cache** | LLM Interface      | XML Format   | Aggregate → Token optimize → Cache | Recommended |

---

## Pros

- **Full Obsidian Integration**: mcp-obsidian provides complete vault access
- **Efficiency**: ChromaDB avoids duplicate crawling
- **LLM Interface**: XML context is LLM-friendly
- **Flexibility**: mcp-obsidian + Rucola combination
- **Pragmatism**: Let LLM handle edge cases

## Cons

- **Two Local Tools**: mcp-obsidian + Rucola
- **Crawl Maintenance**: crawl4ai dependencies

---

## Related Reading

- [mcp-obsidian](https://github.com/bitbonsai/mcp-obsidian) - Obsidian MCP Server
- [Rucola](https://github.com/Linus-Mussmaecher/rucola) - Terminal-based Zettelkasten
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [crawl4ai](https://github.com/unclecode/crawl4ai) - Web crawling
- [Repomix](https://github.com/yl439/repomix)

---

## Next Steps

- [ ] Configure mcp-obsidian for Obsidian vault
- [ ] Integrate mcp-obsidian with Omni MCP
- [ ] Keep Rucola for CLI operations
- [ ] Design External Knowledge workflow (crawl4ai → ChromaDB)
- [ ] Implement Repomix Cache XML schema
