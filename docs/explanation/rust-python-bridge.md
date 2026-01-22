# Rust-Python Bridge

> Trinity Architecture - Foundation Layer Performance Bridge

## Overview

The Rust-Python bridge provides high-performance Rust implementations for performance-critical operations. It uses PyO3 for bindings and is exposed as the `omni-core-rs` Python package.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Python Layer (omni.*)                                       │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  | omni_core_rs                                            |  │
│  |                                                        |  │
│  |  - sniffer: Environment detection                      |  │
│  |  - io: File I/O, token counting                        |  │
│  |  - scanner: Security, skill metadata                   |  │
│  |  - navigation: File outline, code search               |  │
│  |  - editor: Structural refactoring                      |  │
│  |  - vector: LanceDB VectorStore                         |  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ PyO3 Bindings (packages/rust/bindings/python/src/)          │
│  - Python module initialization                             │
│  - Type conversions (Rust ↔ Python)                         │
│  - Error handling                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ Rust Core Crates                                            │
│                                                              │
│  - omni-sniffer: Environment detection                      │
│  - omni-io: Safe I/O, token counting                        │
│  - omni-tags: Pattern extraction                            │
│  - omni-edit: Structural refactoring                        │
│  - omni-vector: LanceDB vector store                        │
└─────────────────────────────────────────────────────────────┘
```

## Available Modules

### Sniffer (Environment Detection)

```python
from omni_core_rs import get_environment_snapshot, PyOmniSniffer

# Get environment snapshot
snapshot = get_environment_snapshot("/project")
# {
#     "git": True,
#     "python": True,
#     "node": False,
#     "languages": [...],
#     "project_type": "..."
# }

# Create sniffer for incremental detection
sniffer = PyOmniSniffer()
sniffer.scan("/workspace")
```

### I/O (File Operations)

```python
from omni_core_rs import read_file_safe, count_tokens, truncate_tokens

# Safe file read (returns tuple)
content, error = read_file_safe("/path/to/file")

# Token counting
token_count = count_tokens("Hello world")

# Truncate to token limit
truncated = truncate_tokens("Long text...", 100)
```

### Scanner (Security & Metadata)

```python
from omni_core_rs import scan_secrets, contains_secrets, scan_skill_tools

# Security scanning
has_secrets, findings = scan_secrets(file_content)

# Skill tool discovery
tools = scan_skill_tools("/assets/skills")
```

### Navigation (Code Analysis)

```python
from omni_core_rs import get_file_outline, search_code, search_directory

# Get code structure
outline = get_file_outline("module.py")
# [{'name': 'MyClass', 'type': 'class', 'lineno': 10}, ...]

# Search code
results = search_code("def process", "/project", [".py"])
```

### Editor (Structural Refactoring)

```python
from omni_core_rs import (
    structural_replace,
    structural_preview,
    structural_apply,
    batch_structural_replace,
)

# Structural replace (AST-based, not regex)
preview = structural_preview(
    code, "old_pattern", "new_pattern",
    file_path="test.py"
)

# Apply changes
result = structural_apply(preview)
```

### Vector Store (LanceDB)

```python
from omni_core_rs import create_vector_store

store = create_vector_store("/cache/vectors", dimension=1536)
store.add_documents("skills", ids, vectors, contents, metadatas)
results = store.search("skills", query_vector, limit=5)
```

## Performance Comparison

| Operation          | Pure Python | Rust Bridge | Speedup  |
| ------------------ | ----------- | ----------- | -------- |
| Token counting     | ~50ms       | ~1ms        | **50×**  |
| Secret scanning    | ~200ms      | ~5ms        | **40×**  |
| File outline       | ~30ms       | ~2ms        | **15×**  |
| Structural replace | N/A         | N/A         | Safe AST |

## Lazy Loading

The bridge uses lazy loading to avoid startup overhead:

```python
# packages/python/foundation/src/omni/foundation/lib.py

def _get_omni_core() -> Any | None:
    """Lazy load Rust core module."""
    try:
        import omni_core_rs
        return omni_core_rs
    except ImportError:
        logger.debug("Rust core not available")
        return None
```

## Error Handling

Rust errors are converted to Python exceptions:

```python
try:
    result = read_file_safe("/path")
except PyErr as e:
    # Handle Rust panic or error
    print(e)
```

## Build System

```bash
# Development build (fast)
just build-rust-dev

# Release build (optimized)
just build-rust-release
```

Output wheel: `target/wheels/omni_core_rs-*.whl`

## Related Files

**Bindings:**

- `packages/rust/bindings/python/src/lib.rs`
- `packages/rust/bindings/python/src/io.rs`
- `packages/rust/bindings/python/src/sniffer.rs`
- `packages/rust/bindings/python/src/scanner.rs`
- `packages/rust/bindings/python/src/vector.rs`

**Rust Crates:**

- `packages/rust/crates/omni-sniffer/`
- `packages/rust/crates/omni-io/`
- `packages/rust/crates/omni-tags/`
- `packages/rust/crates/omni-edit/`
- `packages/rust/crates/omni-vector/`
