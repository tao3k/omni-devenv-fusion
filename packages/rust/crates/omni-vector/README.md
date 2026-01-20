# Omni Vector

> High-Performance Embedded Vector Database using LanceDB.

## Overview

Omni Vector provides vector storage and similarity search capabilities for the Omni DevEnv. It uses LanceDB for efficient disk-based vector storage with ACID guarantees.

## Features

- Disk-based vector storage (no server required)
- Similarity search with cosine similarity
- CRUD operations for vector records
- Schema validation
- Incremental indexing

## Usage

```rust
use omni_vector::{VectorStore, PyVectorRecord};

let store = VectorStore::new("./vectors.lance")?;
let record = PyVectorRecord {
    id: "doc1".to_string(),
    vector: vec![0.1, 0.2, 0.3],
    metadata: serde_json::json!({"source": "docs/readme.md"}),
};

store.add(record)?;
let results = store.search(&vec![0.1, 0.2, 0.3], 5)?;
```

## Architecture

```
omni-vector/
├── lib.rs          # Main API
├── skill.rs        # Skill-specific vector operations
└── scanner.rs      # Vector index scanning
```

## Integration

Used by:

- [Skill Discovery](../../../../docs/llm/skill-discovery.md)
- [Knowledge Matrix](../../../../docs/human/architecture/knowledge-matrix.md)

## See Also

- [docs/reference/librarian.md](../../../../docs/reference/librarian.md)

## License

Apache-2.0
