# Omni Vector

> High-Performance Embedded Vector Database using LanceDB.

## Overview

Omni Vector provides vector storage and similarity search capabilities for the Omni DevEnv. It uses LanceDB for efficient disk-based vector storage with ACID guarantees.

## Features

- Disk-based vector storage (no server required)
- Lance-backed vector similarity search
- Scanner tuning via `SearchOptions`
- CRUD + merge-insert (upsert) operations
- Versioning / snapshot (time travel) APIs
- Schema evolution helpers

## Usage

```rust
use omni_vector::{KeywordSearchBackend, SearchOptions, VectorStore};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut store = VectorStore::new("./vectors", Some(3)).await?;

    store
        .add_documents(
            "skills",
            vec!["doc1".to_string()],
            vec![vec![0.1, 0.2, 0.3]],
            vec!["example document".to_string()],
            vec![serde_json::json!({"source":"docs/readme.md"}).to_string()],
        )
        .await?;

    let results = store
        .search_optimized(
            "skills",
            vec![0.1, 0.2, 0.3],
            5,
            SearchOptions {
                where_filter: Some(r#"{"source":"docs/readme.md"}"#.to_string()),
                ..SearchOptions::default()
            },
        )
        .await?;

    println!("results={}", results.len());

    // Optional: switch keyword backend for hybrid search.
    store.set_keyword_backend(KeywordSearchBackend::LanceFts)?;
    store.create_fts_index("skills").await?;

    Ok(())
}
```

## Architecture

```
omni-vector/
├── src/lib.rs                # Main exports / module wiring
├── src/ops/                  # Core CRUD + admin + writer operations
├── src/search/               # search_optimized + hybrid fusion + search_fts
├── src/keyword/              # keyword backend abstraction (Tantivy / Lance FTS)
└── tests/                    # snapshots + data-layer + perf guard
```

## Integration

Used by:

- [Skill Discovery](../../../../docs/llm/skill-discovery.md)
- [Knowledge Matrix](../../../../docs/human/architecture/knowledge-matrix.md)

## See Also

- [docs/reference/librarian.md](../../../../docs/reference/librarian.md)

## License

Apache-2.0
