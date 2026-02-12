# Zettelkasten-Based Knowledge Architecture

> Discussion document - not a final decision
> Status: Open for debate
> Date: 2026-01-07
> Last Updated: 2026-02-06

---

## Context

Current architecture uses vector database (FAISS) for semantic search. Maintenance burden is high:

- Index rebuilds on content changes
- Embedding model drift
- Database migration complexity

Alternative: Zettelkasten methodology using mcp-obsidian + Rucola + LanceDB.

---

## Three-Dimensional Design Philosophy

### Why zk + Rust + Python (RAG-Anything) is Not Reinventing the Wheel

| Dimension        | Tool                    | Unique Value                                                   |
| ---------------- | ----------------------- | -------------------------------------------------------------- |
| **Zettelkasten** | mcp-obsidian + Rust AST | Structured knowledge, bidirectional links, relationship graph  |
| **Rust Core**    | comrak 0.50             | High-performance AST parsing, zero-copy Arena allocation       |
| **Python/RAG**   | omni-rag                | Flexible query engine, multi-modal processing, semantic search |

### The Synergy: 1 + 1 + 1 > 3

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        THREE-DIMENSIONAL ARCHITECTURE                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     DIMENSION 1: ZK (Structure)                     │    │
│  │                                                                     │    │
│  │   mcp-obsidian provides:                                            │    │
│  │   • Wiki-links (bidirectional references)                           │    │
│  │   • Tags (topic classification)                                     │    │
│  │   • Backlinks (reverse references)                                  │    │
│  │   • Graph (knowledge traversal)                                     │    │
│  │                                                                     │    │
│  │   VALUE: Human-readable, editable, directly usable in Obsidian     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     DIMENSION 2: Rust (Performance)                 │    │
│  │                                                                     │    │
│  │   omni-knowledge provides:                                          │    │
│  │   • comrak 0.50 AST parsing (Rucola-style architecture)             │    │
│  │   • Arena allocation (zero-copy)                                    │    │
│  │   • Single-pass traversal (extract all in one pass)                 │    │
│  │   • Unicode NFC normalization                                       │    │
│  │                                                                     │    │
│  │   VALUE: O(n) complexity, memory-friendly, no runtime regex cost   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   DIMENSION 3: Python/RAG (Intelligence)            │    │
│  │                                                                     │    │
│  │   omni-rag provides:                                                │    │
│  │   • Hybrid search (keyword + semantic)                              │    │
│  │   • Multi-modal chunking (text + image + table)                     │    │
│  │   • Triple integrator (graph + vector + entity)                     │    │
│  │   • Context optimization (LLM-ready chunks)                         │    │
│  │                                                                     │    │
│  │   VALUE: Intelligent retrieval, adaptive chunking, explainable     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### What Makes This Architecture Unique

#### 1. Not Just Parsing, But **Structured Extraction**

Traditional markdown parsers just convert to HTML. We extract **semantic structure**:

```rust
// Input: Markdown with wikilinks and tags
let content = r#"
# Rust Design Patterns

See [[FactoryMethod]] for object creation.
Also [[SingletonPattern]] for single instance.

Tags: #pattern #rust
"#;

// Output: Structured extraction
let extraction = zk::extract(content, true, true);
// ZkExtraction {
//   tags: [ZkTag{name: "pattern"}, ZkTag{name: "rust"}],
//   entities: [ZkEntityRef{name: "FactoryMethod", ...}, ...],
//   wikilinks: ["FactoryMethod", "SingletonPattern"]
// }
```

#### 2. Not Just Storage, But **Relational Knowledge**

```
┌─────────────────────────────────────────────────────────────┐
│                  KNOWLEDGE RELATIONSHIPS                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ZK Layer (mcp-obsidian)                                   │
│   [[WikiLink]] ───→ Bidirectional Reference                 │
│   #tag ────────────→ Topic Classification                   │
│                                                             │
│                    │                                        │
│                    ▼                                        │
│                                                             │
│   Rust Layer (comrak AST)                                   │
│   parse_wikilink() ──→ Entity name + type hint              │
│   extract_entities() ──→ Deduplicated entity set            │
│                                                             │
│                    │                                        │
│                    ▼                                        │
│                                                             │
│   Python Layer (RAG)                                        │
│   graph.search() ──→ Entity relations                       │
│   vector.search() ──→ Semantic similarity                   │
│   triple_integrate() → Unified context                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3. Not Just Search, But **Context-Aware Retrieval**

| Traditional Vector DB    | Our Architecture                        |
| ------------------------ | --------------------------------------- |
| Embedding-only retrieval | Hybrid: keyword + vector + graph        |
| Flat document chunks     | Semantic chunking with entity awareness |
| Black-box relevance      | Explainable: graph path + vector score  |
| Rebuild on changes       | Incremental sync with zk metadata       |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          KNOWLEDGE SYSTEM                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     LOCAL (ZK + Rust)                                 │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │  │  mcp-obsidian  ← Obsidian Vault (Human-Readable)               ││  │
│  │  │  • Notes CRUD                                                   ││  │
│  │  │  • [[Wiki-links]], #tags, backlinks                             ││  │
│  │  │  • Graph traversal                                              ││  │
│  │  └─────────────────────────────────────────────────────────────────┘│  │
│  │                              │                                        │  │
│  │                              ▼                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │  │  Rust Core (omni-knowledge)                                     ││  │
│  │  │  • comrak 0.50 AST parsing (Arena allocation)                   ││  │
│  │  │  • zk::extract() → ZkExtraction (tags + entities + wikilinks)   ││  │
│  │  │  • Zero-copy, single-pass, Unicode-normalized                   ││  │
│  │  │  • PyO3 bindings for Python                                     ││  │
│  │  └─────────────────────────────────────────────────────────────────┘│  │
│  │                                                                     │  │
│  │  VALUE: Human-editable + Machine-parsable + High-performance       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     EXTERNAL (Python/RAG)                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │  │  omni-rag (RAG-Anything)                                        ││  │
│  │  │  • TripleIntegrator: graph + vector + entity                    ││  │
│  │  │  • HybridSearch: keyword + semantic                             ││  │
│  │  │  • MultiModalChunking: text + image + table                     ││  │
│  │  │  • ContextOptimizer: LLM-ready chunks                           ││  │
│  │  └─────────────────────────────────────────────────────────────────┘│  │
│  │                              │                                        │  │
│  │                              ▼                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │  │  LanceDB (Vector Store)                                         ││  │
│  │  │  • Crawled content storage                                      ││  │
│  │  │  • Semantic search index                                        ││  │
│  │  │  • Metadata filtering                                           ││  │
│  │  └─────────────────────────────────────────────────────────────────┘│  │
│  │                                                                     │  │
│  │  VALUE: Intelligent retrieval + Adaptive chunking + Scalable       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Rust Implementation: comrak 0.50 AST Parsing

The `omni-knowledge` crate implements high-performance markdown parsing using [comrak 0.50](https://github.com/kivikakk/comrak.rs), following Rucola's architecture pattern:

### Core Module: `zk.rs`

```rust
// Uses Arena allocation for AST nodes (zero-copy parsing)
use comrak::{format_html, Arena, Options, parse_document};

pub fn extract(content: &str, extract_tags: bool, extract_wikilinks: bool) -> ZkExtraction {
    let arena = Arena::new();
    let options = create_options();
    let root = parse_document(&arena, content, &options);

    // Single AST traversal via descendants()
    for node in root.descendants() {
        let value = &node.data.borrow().value;

        // Extract #hashtags from Text nodes
        if let comrak::nodes::NodeValue::Text(text) = value {
            let text_str: &str = text.as_ref();
            for word in text_str.split_whitespace() {
                if let Some(tag) = word.strip_prefix('#') {
                    // Unicode NFC normalization
                    let normalized: String = tag.nfc().collect();
                    // ...
                }
            }
        }

        // Extract wikilinks from WikiLink nodes
        if let comrak::nodes::NodeValue::WikiLink(wiki_link) = value {
            let url = wiki_link.url.clone();
            // ...
        }
    }
}
```

### Key Features

| Feature                   | Implementation                                          | comrak 0.50 API                   |
| ------------------------- | ------------------------------------------------------- | --------------------------------- |
| **Arena Allocation**      | `Arena::new()` for zero-copy parsing                    | Native support                    |
| **Wikilinks**             | `NodeValue::WikiLink` with `wikilinks_title_after_pipe` | Built-in extension                |
| **Hashtags**              | `NodeValue::Text` traversal via `descendants()`         | Text contains `Cow<'static, str>` |
| **Unicode Normalization** | `unicode-normalization` crate                           | NFC normalization                 |

### Extracted Types

```rust
// Tag extracted from #hashtag
pub struct ZkTag {
    pub name: String,  // e.g., "rust" from "#rust"
}

// Entity reference from [[WikiLink]]
pub struct ZkEntityRef {
    pub name: String,              // Entity name
    pub entity_type: Option<String>, // e.g., "rust", "py", "pattern"
    pub original: String,           // "[[EntityName#type]]"
}

// Combined extraction result
pub struct ZkExtraction {
    pub tags: Vec<ZkTag>,
    pub entities: Vec<ZkEntityRef>,
    pub wikilinks: Vec<String>,
}
```

### Modular Structure

```
packages/rust/crates/omni-knowledge/src/
├── lib.rs              # Main module, registers PyO3 bindings
├── zk.rs               # Core extraction logic (pure Rust)
├── zk_py.rs           # PyO3 bindings (Python integration)
├── entity.rs           # Knowledge graph entities
├── graph.rs            # Knowledge graph operations
├── storage.rs          # LanceDB storage
└── sync.rs            # Incremental sync engine
```

### PyO3 Module Registration

```rust
// lib.rs
pub mod zk;
mod zk_py;

#[pymodule]
fn _omni_knowledge(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    zk_py::register_zk_module(_py, m)?;
    Ok(())
}

// zk_py.rs
pub fn register_zk_module(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyZkTag>()?;
    m.add_class::<PyZkEntityRef>()?;
    m.add_function(wrap_pyfunction!(zk_extract, py)?)?;
    // ...
    Ok(())
}
```

### Python API

```python
from omni_knowledge import zk_extract, zk_extract_tags, zk_extract_entities

# Extract all from markdown
result = zk_extract(content, extract_tags=True, extract_wikilinks=True)
# → PyZkExtraction { tags: [...], entities: [...], wikilinks: [...] }

# Extract only tags
tags = zk_extract_tags(content)
# → [PyZkTag { name: "rust" }, ...]

# Extract entities
entities = zk_extract_entities(content)
# → [PyZkEntityRef { name: "FactoryPattern", entity_type: "py" }, ...]
```

### Wikilink Parsing

```rust
// Supports: [[Name]], [[Name#type]], [[Name|alias]], [[Name#type|alias]]
pub fn parse_wikilink(url: &str) -> (String, Option<String>) {
    // [[EntityName#type|alias]] → ("EntityName", Some("type"))
    // [[Name|alias]] → ("Name", None)
    // [[Name]] → ("Name", None)
}
```

### Tests

Located at `packages/rust/crates/omni-knowledge/tests/test_zk.rs`:

```bash
cargo test -p omni-knowledge --test test_zk
# → 21 passed, 0 failed
```

| Test Category | Coverage                                   |
| ------------- | ------------------------------------------ |
| **Wikilinks** | Basic, typed, aliases, deduplication       |
| **Tags**      | Single, multi-word, combined extraction    |
| **Entities**  | Type hints, parsing, conversion methods    |
| **Stats**     | Tag count, wikilink count, unique entities |
| **Utilities** | `is_wikilink()`, `parse_wikilink_text()`   |

---

## Role Division

| Tool             | Role                 | Responsibility                          |
| ---------------- | -------------------- | --------------------------------------- |
| **mcp-obsidian** | Obsidian Integration | Notes CRUD, wiki-links, graph, search   |
| **Rucola**       | CLI Helper           | Quick operations, stats, CLI management |
| **LanceDB**      | External Knowledge   | Crawled content, semantic search        |

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

## External Knowledge: LanceDB

**Input**: Crawled content from crawl4ai, GitHub repos, PDFs, APIs
**Output**: Searchable vector store with metadata

**Workflow**:

```
Source: GitHub Repo, Web Page, PDF, API Doc
    │
    ▼
┌─────────────────┐     ┌─────────────────────┐
│ Repomix (Full)  │────▶│   LanceDB           │  ← Store complete content
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
                        │ 2. Get from LanceDB │
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
| **LanceDB**       | External Knowledge | Vector Store | Crawled content, research          | Required    |
| **Repomix Cache** | LLM Interface      | XML Format   | Aggregate → Token optimize → Cache | Recommended |

---

## Pros

- **Full Obsidian Integration**: mcp-obsidian provides complete vault access
- **Efficiency**: LanceDB avoids duplicate crawling
- **LLM Interface**: XML context is LLM-friendly
- **Flexibility**: mcp-obsidian + Rucola combination
- **Pragmatism**: Let LLM handle edge cases

## Cons

- **Two Local Tools**: mcp-obsidian + Rucola
- **Crawl Maintenance**: crawl4ai dependencies

---

## Related Reading

- [comrak.rs](https://github.com/kivikakk/comrak.rs) - CommonMark parser (used for zk extraction)
- [mcp-obsidian](https://github.com/bitbonsai/mcp-obsidian) - Obsidian MCP Server
- [Rucola](https://github.com/Linus-Mussmaecher/rucola) - Terminal-based Zettelkasten (inspiration for comrak approach)
- [ChromaDB](https://www.trychroma.com/) - Vector database (replaced by LanceDB)
- [crawl4ai](https://github.com/unclecode/crawl4ai) - Web crawling
- [Repomix](https://github.com/yl439/repomix)

---

## Next Steps

### Completed

- [x] Implement Rust `zk` module with comrak 0.50 AST parsing
- [x] Add PyO3 bindings for Python integration
- [x] Create 21 comprehensive unit tests
- [x] Modularize code (zk.rs + zk_py.rs separation)

### Pending

- [ ] Configure mcp-obsidian for Obsidian vault
- [ ] Integrate mcp-obsidian with Omni MCP
- [ ] Keep Rucola for CLI operations
- [ ] Design External Knowledge workflow (crawl4ai → LanceDB)
- [ ] Implement Repomix Cache XML schema
