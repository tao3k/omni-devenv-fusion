# Librarian

> Unified Knowledge Ingestion with Smart Incremental Support

## Overview

The `Librarian` class provides unified knowledge ingestion with **smart incremental support**:

| Feature                   | Description                                                                |
| ------------------------- | -------------------------------------------------------------------------- |
| **Chunk Modes**           | `AUTO` (auto-detect), `TEXT` (docs), `AST` (code)                          |
| **Incremental Ingestion** | Only processes changed files (O(1) update)                                 |
| **Manifest Tracking**     | Hash-based change detection via `.cache/knowledge/knowledge_manifest.json` |
| **Hot Indexing**          | Single file updates via `upsert_file()` for watcher integration            |

## Architecture

```
Librarian
    ├── Config: references.yaml settings
    ├── Chunking: Text (docs) or AST (code) modes
    ├── Manifest: Hash-based change tracking (.cache/knowledge/)
    └── Storage: LanceDB operations (.cache/omni-vector/)
```

## Usage

### Basic Ingestion

```python
from omni.core.knowledge import Librarian, ChunkMode

# Initialize (uses AUTO mode by default)
librarian = Librarian(project_root=".")

# First time: Full ingestion
result = librarian.ingest(clean=True)
# Returns: {"files_processed": 100, "chunks_indexed": 500, "errors": 0, "updated": 100}

# Subsequent runs: Incremental (only changed files)
result = librarian.ingest()
# If no changes: {"files_processed": 0, "chunks_indexed": 0, "errors": 0, "updated": 0}
```

### Chunk Modes

```python
# AUTO: Detect file type (code=AST, docs=TEXT) - DEFAULT
librarian = Librarian(project_root=".", chunk_mode=ChunkMode.AUTO)

# AST: Force Rust AST chunking for code
librarian = Librarian(project_root=".", chunk_mode=ChunkMode.AST)

# TEXT: Force text chunking for documentation
librarian = Librarian(project_root=".", chunk_mode=ChunkMode.TEXT)
```

### Hot Indexing (Watcher Integration)

```python
# For file watcher integration - update a single file immediately
librarian.upsert_file("/path/to/changed/file.py")
# Returns True if indexed, False if unchanged (debounced)
```

### Query & Context

```python
# Search knowledge base
results = librarian.query("How does the router work?", limit=5)

# Get LLM-ready context blocks
context = librarian.get_context("connect_to_db function", limit=3)

# Get statistics
stats = librarian.get_stats()
# Returns: {"table": "knowledge_chunks", "record_count": 500, "tracked_files": 100}

# Get manifest status
status = librarian.get_manifest_status()
# Returns: {"manifest_path": ".cache/omni-vector/knowledge_manifest.json", ...}
```

## CLI Commands

```bash
# Full ingestion (first time)
omni knowledge ingest . --clean

# Incremental ingestion (default)
omni knowledge ingest .

# Get context for LLM
omni knowledge context "How does the router work?" -l 3

# Show stats
omni knowledge stats
```

## Manifest Tracking

The Librarian uses a manifest file to track file changes:

- **Location**: `.cache/omni-vector/knowledge_manifest.json`
- **Format**: `{ "rel/path/file.py": "md5_hash", ... }`
- **Behavior**:
  - On first run: Full scan, create manifest
  - On subsequent runs: Only process files with changed hashes
  - Automatic cleanup: Detect deleted files and remove from index

### Performance

| Scenario         | Time Complexity | Example (1000 files) |
| ---------------- | --------------- | -------------------- |
| First run        | O(n)            | ~2-5 minutes         |
| No changes       | O(1)            | Instant              |
| One file changed | O(1)            | ~1-2 seconds         |
| File deleted     | O(1)            | Instant              |

## Configuration

Reads from `references.yaml`:

```yaml
knowledge_dirs:
  - path: "assets/knowledge"
    domain: "knowledge"
  - path: "assets/how-to"
    domain: "workflow"
  - path: "docs/explanation"
    domain: "architecture"
  - path: "packages"
    domain: "code"
```

## Supported Languages (AST Mode)

| Extension | Language   | Patterns                                         |
| --------- | ---------- | ------------------------------------------------ |
| `.py`     | Python     | `def $NAME`, `class $NAME`                       |
| `.rs`     | Rust       | `pub fn $NAME`, `pub struct $NAME`, `impl $NAME` |
| `.js`     | JavaScript | `function $NAME`, `class $NAME`                  |
| `.ts`     | TypeScript | `function $NAME`, `class $NAME`                  |
| `.go`     | Go         | `func $NAME`, `type $NAME struct`                |
| `.java`   | Java       | `public $NAME`, `class $NAME`                    |

## Skip Directories

Automatically skipped:

- `node_modules`, `.git`, `__pycache__`
- `target`, `build`, `.gradle`
- `.venv`, `venv`, `.cache`
- `dist`, `out`, `.idea`

## Database Path

Uses unified storage in `.cache/omni-vector/`:

- **Vector DB**: `.cache/omni-vector/knowledge.lance`
- **Manifest**: `.cache/omni-vector/knowledge_manifest.json`

## File Structure

```
packages/python/core/src/omni/core/knowledge/
├── __init__.py              # Exports: Librarian, ChunkMode, FileIngestor
├── config.py                # KnowledgeConfig from references.yaml
├── ingestion.py             # FileIngestor: discovery + chunking
├── storage.py               # KnowledgeStorage: LanceDB operations
└── librarian.py             # Librarian main class (with incremental support)
```

## Integration with Watcher

For real-time updates, integrate with the file watcher:

```python
from omni.core.knowledge import Librarian

librarian = Librarian(project_root=".")

# In your watcher callback:
def on_file_change(file_path: str, event_type: str):
    if file_path.endswith((".py", ".rs", ".md")):
        librarian.upsert_file(file_path)
```

## Related Documentation

- [Knowledge Matrix](../human/architecture/knowledge-matrix.md) - Unified knowledge architecture
- [AST-grep Core](../developer/ast-grep-core.md) - Semantic code analysis
- [RAG Search](../reference/rag-search.md) - Search protocols
