# Rust Crates - Omni-Dev-Fusion

> High-performance Rust crates for Omni-Dev-Fusion
> Last Updated: 2026-02-01

---

## Table of Contents

1. [Overview](#overview)
2. [Crate Directory](#crate-directory)
3. [Individual Crates](#individual-crates)
   - [omni-ast](#omni-ast)
   - [omni-edit](#omni-edit)
   - [omni-io](#omni-io)
   - [omni-lance](#omni-lance)
   - [omni-security](#omni-security)
   - [omni-sniffer](#omni-sniffer)
   - [omni-tags](#omni-tags)
   - [omni-tokenizer](#omni-tokenizer)
   - [omni-types](#omni-types)
   - [omni-vector](#omni-vector)
   - [skills-scanner](#skills-scanner)
4. [Python Bindings](#python-bindings)
5. [Build Commands](#build-commands)

---

## Overview

The Rust crates provide high-performance implementations for performance-critical operations:

| Crate            | Purpose                | Key Dependencies     |
| ---------------- | ---------------------- | -------------------- |
| `omni-ast`       | AST utilities          | ast-grep-core        |
| `omni-edit`      | Structural refactoring | ast-grep, rayon      |
| `omni-io`        | File I/O               | tokio, memchr        |
| `omni-lance`     | LanceDB utilities      | lance                |
| `omni-security`  | Secret scanning        | regex                |
| `omni-sniffer`   | Environment sniffer    | git2                 |
| `omni-tags`      | Symbol extraction      | tree-sitter, walkdir |
| `omni-tokenizer` | Token counting         | tiktoken-rs          |
| `omni-types`     | Common types           | serde                |
| `omni-vector`    | Vector database        | lance, dashmap       |
| `skills-scanner` | Skill scanning         | omni-ast             |

---

## Crate Directory

```
packages/rust/crates/
├── omni-ast/              # Unified AST utilities using ast-grep
├── omni-edit/             # Structural refactoring (The Surgeon)
├── omni-io/               # File I/O utilities with encoding detection
├── omni-lance/            # LanceDB RecordBatch utilities
├── omni-security/         # High-performance secret scanning
├── omni-sniffer/          # Environment sniffer (Git + scratchpad)
├── omni-tags/             # Code symbol extraction (The Cartographer)
├── omni-tokenizer/        # Token counting (tiktoken)
├── omni-types/            # Common type definitions
├── omni-vector/           # High-Performance Vector Database (LanceDB)
└── skills-scanner/        # Modular skill directory scanning
```

---

## Individual Crates

### omni-ast

**Purpose**: Unified AST utilities using ast-grep (v0.40.5) + Security Scanner

**Location**: `packages/rust/crates/omni-ast/`

```
omni-ast/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Re-exports entry point
│   ├── lang.rs            # Lang enum and language support
│   ├── scan.rs            # Pattern utilities
│   ├── python.py          # Python-specific utilities
│   ├── item.rs            # Match struct
│   ├── security.rs        # Security Scanner (Level 1 Defense)
│   └── re_exports.rs      # ast-grep re-exports
└── tests/
    └── test_ast.rs
```

**Key Dependencies**:

- `ast-grep-core`
- `ast-grep-language`

**Key Exports**:

```rust
pub struct Lang { /* Language enum */ }
pub struct Match { /* AST match result */ }

// Security Scanner
pub struct SecurityScanner {
    pub fn new() -> Self;
    pub fn scan(&self, code: &str) -> Result<(), SecurityViolation>;
    pub fn scan_all(&self, code: &str) -> Vec<SecurityViolation>;
}

pub struct SecurityViolation {
    pub rule_id: String,      // e.g., "SEC-IMPORT-001"
    pub description: String,
    pub line: usize,
    pub snippet: String,
}
```

**Security Rules** (detected by `SecurityScanner`):

| Category            | Patterns                                  | Example              |
| ------------------- | ----------------------------------------- | -------------------- |
| Forbidden Imports   | `os`, `subprocess`, `socket`, `ctypes`    | `import os`          |
| Dangerous Calls     | `eval()`, `exec()`, `compile()`, `open()` | `eval(code)`         |
| Suspicious Patterns | `getattr()`, `setattr()`, `globals()`     | `getattr(obj, name)` |

**Python Bindings** (`packages/rust/bindings/python/src/security.rs`):

```python
from omni_core_rs import scan_code_security, is_code_safe

# Scan code for security violations
is_safe, violations = scan_code_security(code)
# Returns: (is_safe: bool, violations: list[dict])

# Quick boolean check
if is_code_safe(code):
    print("Code passed security checks")
```

**Performance**:

| Operation                   | Time  | Throughput     |
| --------------------------- | ----- | -------------- |
| Security scan (1 file, 5KB) | ~1ms  | -              |
| Security scan (100 files)   | ~50ms | 2000 files/sec |

---

### omni-edit

**Purpose**: Structural refactoring (The Surgeon + The Ouroboros)

**Location**: `packages/rust/crates/omni-edit/`

```
omni-edit/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Entry point
│   ├── editor.rs          # Single file editing with diff preview
│   ├── batch.rs           # Batch refactoring with rayon parallelism
│   ├── diff.rs            # Diff generation
│   ├── capture.rs         # AST capture utilities
│   ├── types.rs           # Type definitions
│   └── error.rs           # Error types
└── tests/
    └── test_edit.rs
```

**Key Dependencies**:

- `omni-ast`
- `similar` (diff algorithm)
- `rayon` (parallelism)
- `ignore`
- `dashmap`

**Key Exports**:

```rust
pub struct Editor { /* Single file editing */ }
pub struct BatchEditor { /* Batch refactoring */ }
pub struct Diff { /* Diff result */ }
```

---

### omni-io

**Purpose**: File I/O utilities with encoding detection

**Location**: `packages/rust/crates/omni-io/`

```
omni-io/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Entry point
│   ├── error.rs           # Error types
│   ├── detect.rs          # File encoding detection
│   ├── async_io.rs        # Async I/O operations
│   └── sync.rs            # Sync I/O operations
└── tests/
    └── test_io.rs
```

**Key Dependencies**:

- `memchr` (encoding detection)
- `tokio` (async I/O)

**Key Exports**:

```rust
pub fn detect_encoding(path: &Path) -> Result<Encoding>;
pub async fn read_file_async(path: &Path) -> Result<String>;
```

---

### omni-lance

**Purpose**: LanceDB RecordBatch utilities

**Location**: `packages/rust/crates/omni-lance/`

```
omni-lance/
├── Cargo.toml
├── src/
│   └── lib.rs             # Entry point (only file)
└── tests/
    └── test_lance.rs
```

**Key Dependencies**:

- `lance`

**Key Exports**:

```rust
pub fn record_batch_to_bytes(batch: &RecordBatch) -> Vec<u8>;
pub fn bytes_to_record_batch(bytes: &[u8]) -> Result<RecordBatch>;
```

---

### omni-security

**Purpose**: High-performance secret scanning (DFA regex, O(n) scanning)

**Location**: `packages/rust/crates/omni-security/`

```
omni-security/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Entry point with SecretScanner
│   └── error.rs           # Error types
└── tests/
    └── test_security.rs
```

**Patterns Detected**:

- AWS Access Key (`AKIA...`)
- Stripe Secret Key (`sk_live_...`)
- Slack Token (`xoxb-...`)
- PEM Private Key (`-----BEGIN.*PRIVATE KEY-----`)
- Generic API Keys

**Key Dependencies**:

- `regex` (DFA regex for O(n) scanning)
- `once_cell`

**Key Exports**:

```rust
pub struct SecretScanner {
    pub patterns: Vec<SecretPattern>,
    pub scan(&self, content: &str) -> Vec<SecretMatch>,
}
```

---

### omni-sniffer

**Purpose**: High-performance environment sniffer for Omni DevEnv

**Location**: `packages/rust/crates/omni-sniffer/`

```
omni-sniffer/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Re-exports entry point
│   ├── sniffer.rs         # OmniSniffer struct
│   ├── git.rs             # Git status scanning
│   ├── context.rs         # Scratchpad scanning
│   └── error.rs           # SnifferError enum
└── tests/
    └── test_sniffer.rs
```

**Key Dependencies**:

- `git2` (Git operations)
- `omni-types`

**Key Exports**:

```rust
pub struct OmniSniffer {
    pub fn sniff_git(&self) -> Result<GitSnapshot>;
    pub fn sniff_context(&self, path: &Path) -> Result<ContextSnapshot>;
}
```

---

### omni-tags

**Purpose**: High-Performance Code Symbol Extraction (The Cartographer + The Hunter)

**Location**: `packages/rust/crates/omni-tags/`

```
omni-tags/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Re-exports entry point
│   ├── extractor.rs       # TagExtractor with all methods
│   ├── types.rs           # SymbolKind, Symbol, SearchMatch, SearchConfig
│   ├── patterns.rs        # ast-grep pattern constants
│   └── error.rs           # TagError, SearchError
└── tests/
    └── test_tags.rs
```

**Supported Languages**:

- Python
- Rust
- JavaScript
- TypeScript

**Key Dependencies**:

- `omni-ast` (ast-grep-core 0.40.5)
- `tree-sitter`
- `walkdir`

**Key Exports**:

```rust
pub struct TagExtractor;

impl TagExtractor {
    /// Generate symbolic outline for a file
    pub fn outline_file<P: AsRef<Path>>(
        path: P,
        language: Option<&str>
    ) -> Result<String, TagError>;

    /// Search AST patterns in a single file
    pub fn search_file<P: AsRef<Path>>(
        path: P,
        pattern: &str,
        language: Option<&str>
    ) -> Result<String, SearchError>;

    /// Recursive AST search in directory
    pub fn search_directory<P: AsRef<Path>>(
        dir: P,
        pattern: &str,
        config: SearchConfig
    ) -> Result<String, SearchError>;
}

pub enum SymbolKind {
    Function,
    AsyncFunction,
    Class,
    Struct,
    Method,
    Trait,
    Impl,
    Module,
    Enum,
    Interface,
    Unknown,
}

pub struct Symbol {
    pub name: String,
    pub kind: SymbolKind,
    pub line: usize,
    pub signature: String,
}

pub struct SearchMatch {
    pub path: String,
    pub line: usize,
    pub column: usize,
    pub content: String,
    pub captures: HashMap<String, String>,
}

pub struct SearchConfig {
    pub file_pattern: String,
    pub max_file_size: u64,
    pub max_matches_per_file: usize,
    pub languages: Vec<String>,
}
```

**Python Bindings** (`packages/rust/bindings/python/src/navigation.rs`):

```python
from omni_core_rs import (
    get_file_outline,
    search_code,
    search_directory,
)
```

**Pattern Constants** (`packages/rust/crates/omni-tags/src/patterns.rs`):

```rust
// Python patterns
pub const PYTHON_CLASS_PATTERN: &str = "class $NAME";
pub const PYTHON_DEF_PATTERN: &str = "def $NAME($PARAMS)";
pub const PYTHON_ASYNC_DEF_PATTERN: &str = "async def $NAME($PARAMS)";

// Rust patterns
pub const RUST_STRUCT_PATTERN: &str = "struct $NAME";
pub const RUST_FN_PATTERN: &str = "fn $NAME($PARAMS)";
pub const RUST_ENUM_PATTERN: &str = "enum $NAME";
pub const RUST_TRAIT_PATTERN: &str = "trait $NAME";
pub const RUST_IMPL_PATTERN: &str = "impl$NAME";

// JS/TS patterns
pub const JS_CLASS_PATTERN: &str = "class $NAME";
pub const JS_FN_PATTERN: &str = "function $NAME($PARAMS)";
pub const TS_INTERFACE_PATTERN: &str = "interface $NAME";
```

**Performance**:

| Operation                | Time  | Throughput     |
| ------------------------ | ----- | -------------- |
| Outline (1 file, 5KB)    | ~3ms  | -              |
| Search (100 files)       | ~50ms | 2000 files/sec |
| Extract symbols (1 file) | ~1ms  | -              |

---

### omni-edit

**Purpose**: Structural Search & Replace (The Surgeon + The Ouroboros)

**Location**: `packages/rust/crates/omni-edit/`

```
omni-edit/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Entry point
│   ├── editor.rs          # Single file editing
│   ├── batch.rs           # Batch refactoring
│   ├── diff.rs            # Diff generation
│   ├── capture.rs         # AST capture utilities
│   ├── types.rs           # Type definitions
│   └── error.rs           # Error types
└── tests/
    └── test_edit.rs
```

**Key Dependencies**:

- `omni-ast` (ast-grep-core 0.40.5)
- `similar` (diff algorithm)
- `rayon` (parallelism)
- `ignore` (file traversal)
- `dashmap` (thread-safe counters)

**Key Exports**:

```rust
pub struct StructuralEditor;

impl StructuralEditor {
    /// Replace pattern in content string
    pub fn replace(
        &self,
        code: &str,
        lang: &str,
        pattern: &str,
        rewrite: &str
    ) -> String;

    /// Preview changes (returns diff)
    pub fn preview<P: AsRef<Path>>(
        &self,
        path: P,
        pattern: &str,
        rewrite: &str,
        language: Option<&str>
    ) -> Result<String, EditError>;

    /// Apply changes to file
    pub fn apply<P: AsRef<Path>>(
        &self,
        path: P,
        pattern: &str,
        rewrite: &str,
        language: Option<&str>
    ) -> Result<String, EditError>;
}

pub struct BatchRefactorStats {
    pub files_scanned: usize,
    pub files_changed: usize,
    pub replacements: usize,
    pub modified_files: Vec<String>,
    pub errors: Vec<String>,
}

pub struct BatchEditor {
    /// Parallel refactoring across directory
    pub fn replace<P: AsRef<Path>>(
        &self,
        root: P,
        pattern: &str,
        rewrite: &str,
        file_pattern: &str,
        dry_run: bool
    ) -> BatchRefactorStats;
}
```

**Python Bindings** (`packages/rust/bindings/python/src/editor.rs`):

```python
from omni_core_rs import (
    structural_replace,    # Replace in string
    structural_preview,    # Preview (dry-run)
    structural_apply,      # Apply to file
    batch_structural_replace,  # Batch refactor
)
```

**Pattern Syntax**:

| Pattern   | Meaning           | Example Match     |
| --------- | ----------------- | ----------------- |
| `$NAME`   | Single identifier | `foo`, `MyClass`  |
| `$ARGS`   | Argument list     | `(a, b, c)`       |
| `$PARAMS` | Parameter list    | `(data, options)` |
| `$$$`     | Variadic match    | `(host, port)`    |
| `$$$ARGS` | Named variadic    | `(x, y, z)`       |

**Rewrite Templates**:

```rust
// Simple replacement
pattern: "print($$$ARGS)"
rewrite: "logger.info($$$ARGS)"

// With transformations
pattern: "connect($HOST, $PORT)"
rewrite: "safe_connect($HOST, $PORT, timeout=30)"

// Class rename
pattern: "OldClass"
rewrite: "NewClass"

// Function wrapper
pattern: "old_api($$$ARGS)"
rewrite: "wrapper($$$ARGS)"
```

**Performance**:

| Operation           | Time   | Parallelism |
| ------------------- | ------ | ----------- |
| Single file replace | ~2ms   | -           |
| Preview (dry-run)   | ~5ms   | -           |
| Apply to file       | ~3ms   | -           |
| Batch (100 files)   | ~100ms | rayon       |
| Batch (1000 files)  | ~500ms | rayon       |

---

### omni-tokenizer

**Purpose**: High-performance token counting and context pruning

**Location**: `packages/rust/crates/omni-tokenizer/`

```
omni-tokenizer/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Entry point
│   ├── tokenizer.rs       # TokenCounter (cl100k_base)
│   ├── pruner.rs          # ContextPruner (message compression)
│   └── error.rs           # Error types
└── tests/
    └── test_tokenizer.rs
```

**Key Dependencies**:

- `tiktoken-rs` (OpenAI's tiktoken encoding)
- `serde` (serialization)

**Key Exports**:

```rust
// Token counting (cl100k_base - GPT-4/3.5 standard)
pub fn count_tokens(content: &str) -> usize;
pub fn truncate(content: &str, max_tokens: usize) -> String;
pub fn truncate_middle(content: &str, max_tokens: usize) -> String;

// Message struct for conversation history
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

// Context pruning for LangGraph workflows
pub struct ContextPruner {
    tokenizer: TokenCounter,
    window_size: usize,
    max_tool_output: usize,
}

impl ContextPruner {
    pub fn new(window_size: usize, max_tool_output: usize) -> Self;
    pub fn compress(&self, messages: Vec<Message>) -> Vec<Message>;
    pub fn count_tokens(&self, text: &str) -> usize;
}
```

**Compression Strategy**:

1. **Always preserve** system messages
2. **Keep last N\*2 messages** as working memory
3. **Truncate tool outputs** in archive (older messages) to `max_tool_output` chars
4. **Reassemble**: `[System] + [Processed Archive] + [Working Memory]`

**Performance**:

| Operation             | Performance                         |
| --------------------- | ----------------------------------- |
| Token counting        | 20-100x faster than Python tiktoken |
| Message compression   | <1ms for typical conversations      |
| 1000 char tool output | ~0.1ms to compress                  |

**Python Bindings** (`packages/rust/bindings/python/src/tokenizer.rs`):

```python
from omni_core_rs.tokenizer import (
    py_count_tokens,
    py_truncate,
    py_truncate_middle,
    PyContextPruner,
)

# Token counting
count = py_count_tokens("Hello, world!")  # Returns token count

# Context pruner
pruner = PyContextPruner(window_size=4, max_tool_output=500)
compressed = pruner.compress([{"role": "user", "content": "..."}])
```

---

### omni-types

**Purpose**: Common type definitions for Omni DevEnv

**Location**: `packages/rust/crates/omni-types/`

```
omni-types/
├── Cargo.toml
├── src/
│   └── lib.rs             # Entry point with all types
└── tests/
    └── test_types.rs
```

**Key Types**:

```rust
pub struct OmniError {
    pub code: ErrorCode,
    pub message: String,
    pub context: Option<Value>,
}

pub struct Skill {
    pub name: String,
    pub description: String,
    pub commands: Vec<Command>,
}

pub struct TaskBrief {
    pub task_id: String,
    pub description: String,
    pub context: Value,
}

pub struct AgentResult {
    pub success: bool,
    pub output: String,
    pub metrics: Option<ExecutionMetrics>,
}

pub struct VectorSearchResult {
    pub id: String,
    pub score: f32,
    pub payload: Value,
    pub metadata: HashMap<String, String>,
}

pub struct EnvironmentSnapshot {
    pub git_status: Option<GitStatus>,
    pub working_directory: PathBuf,
    pub timestamp: DateTime<Utc>,
    pub context_files: Vec<PathBuf>,
}
```

**Key Dependencies**:

- `serde`, `serde_json`
- `thiserror`

---

### omni-vector

**Purpose**: High-Performance Embedded Vector Database using LanceDB

**Location**: `packages/rust/crates/omni-vector/`

```
omni-vector/
├── Cargo.toml
├── src/
│   ├── lib.rs             # VectorStore struct
│   ├── store.rs           # CRUD operations (add/delete/count)
│   ├── search.rs          # Search operations
│   ├── index.rs           # Index creation operations
│   ├── skill.rs           # Skill tool indexing
│   ├── batch.rs           # RecordBatch utilities
│   └── error.rs           # VectorStoreError enum
└── tests/
    └── test_vector.rs
```

**Key Operations**:

- `add(documents, ids, metadatas)` - Add documents
- `search(query, n_results, where_filter)` - Search with filtering
- `delete(ids)` - Delete by IDs
- `count()` - Count documents
- `create_index(column, metric_type)` - Create index

**Key Dependencies**:

- `lance`
- `omni-lance`
- `skills-scanner`
- `dashmap` (thread-safe storage)
- `tokio` (async operations)

**Key Exports**:

```rust
pub struct VectorStore {
    pub uri: String,
    pub dimension: usize,
    pub async fn add(&self, collection: &str, documents: &[String], ...);
    pub async fn search(&self, collection: &str, query: &str, ...) -> Vec<VectorSearchResult>;
}
```

---

### skills-scanner

**Purpose**: Modular skill directory scanning for Omni-Dev-Fusion

**Location**: `packages/rust/crates/skills-scanner/`

```
skills-scanner/
├── Cargo.toml
├── src/
│   ├── lib.rs             # Main module and exports
│   ├── skill_scanner.rs   # SKILL.md parser
│   ├── script_scanner.rs  # @skill_command script parser
│   ├── skill_metadata.rs  # SkillMetadata, ToolRecord, ScanConfig
│   ├── document_scanner.rs # Directory inventory scanning
│   ├── reference_path.rs  # Reference path handling
│   └── error.rs           # Scanner errors
└── tests/
    └── test_scanner.rs
```

**Key Re-exports**:

```rust
pub use skill_scanner::SkillScanner;
pub use script_scanner::ScriptScanner;
pub use skill_metadata::{SkillMetadata, ToolRecord, ScanConfig};
pub use document_scanner::{DocumentScanner, FileEntry};
pub use reference_path::ReferencePath;
```

**Key Dependencies**:

- `omni-ast`
- `serde`, `serde_yaml`
- `schemars`
- `tokio`
- `sha2`

---

## Python Bindings

**Location**: `packages/rust/bindings/python/`

```
packages/rust/bindings/python/
├── Cargo.toml
├── src/
│   ├── lib.rs             # PyO3 module entry point
│   ├── lib.rs             # Python module definition
│   ├── scanner.rs         # Scanner bindings
│   ├── vector.rs          # Vector store bindings
│   ├── sniffer.rs         # Sniffer bindings
│   ├── editor.rs          # Editor bindings
│   ├── navigation.rs      # Navigation bindings
│   ├── tags.rs            # Tags bindings
│   └── ...
└── pyproject.toml         # Python package config
```

**Build**:

```bash
# Development build (fast)
just build-rust-dev

# Release build
cargo build --release -p omni-python-bindings
```

---

## Build Commands

### Development

```bash
# Build all crates in debug mode
cargo build --workspace

# Build specific crate
cargo build -p omni-vector

# Watch mode (requires cargo-watch)
cargo watch -x build
```

### Testing

```bash
# Run all Rust tests
cargo test --workspace

# Run specific crate tests
cargo test -p omni-vector
cargo test -p omni-tags
cargo test -p omni-edit

# With output
cargo test -p omni-vector -- --nocapture
```

### Release

```bash
# Release build all
cargo build --release --workspace

# Build Python bindings
cargo build --release -p omni-python-bindings
```

### Benchmarks

```bash
# Run benchmarks
cargo bench -p omni-vector
cargo bench -p omni-tags
```

---

## Performance Characteristics

| Crate            | Operation         | Performance                |
| ---------------- | ----------------- | -------------------------- |
| `omni-vector`    | Vector search     | ~1ms for 10K vectors       |
| `omni-tags`      | Symbol extraction | ~10ms for 1000 files       |
| `omni-edit`      | Batch refactor    | O(n) with rayon parallel   |
| `omni-security`  | Secret scan       | O(n) DFA regex             |
| `omni-sniffer`   | Git status        | ~5ms                       |
| `omni-tokenizer` | Token counting    | 20-100x faster than Python |
| `omni-tokenizer` | Message compress  | <1ms for typical conv      |

---

## Related Documentation

- [Codebase Structure](codebase-structure.md)
- [Skills System](skills.md)
- [Project Execution Standard](../reference/project-execution-standard.md)
- [Engineering Protocol](../reference/odf-ep-protocol.md)
