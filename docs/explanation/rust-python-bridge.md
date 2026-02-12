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
│  |  - events: Global Event Bus (GLOBAL_BUS)               |  │
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
│  - omni-events: Global Event Bus (tokio broadcast)          │
│  - omni-sniffer: Environment detection                      │
│  - omni-io: Safe I/O, token counting                        │
│  - omni-tags: Pattern extraction                            │
│  - omni-edit: Structural refactoring                        │
│  - omni-vector: LanceDB vector store                        │
└─────────────────────────────────────────────────────────────┘
```

### Event Bus (v5.0 - The Grand Integration)

**Location**: `packages/rust/crates/omni-events/`

The Event Bus enables cross-language reactive architecture:

```python
from omni_core_rs import PyGlobalEventBus

# Publish event (fire-and-forget)
payload = '{"thread_id": "session-123", "step": 1, "state": {...}}'
PyGlobalEventBus.publish("agent", "agent/step_complete", payload)
```

#### Event Topics

| Topic                 | Source     | Purpose            |
| --------------------- | ---------- | ------------------ |
| `file/changed`        | Watcher    | File modification  |
| `file/created`        | Watcher    | New file           |
| `agent/step_complete` | Agent Loop | Checkpoint trigger |
| `context/updated`     | Sniffer    | Context change     |

#### Architecture

```
Rust GLOBAL_BUS.publish("source", "topic", payload)
              ↓ (tokio broadcast - non-blocking)
Python: PyGlobalEventBus.publish()
              ↓
KernelReactor._consumer_loop()
              ↓
Handlers: Cortex, Sniffer, Checkpoint
```

## Available Modules

### Event Bus (Global Event Bus)

```python
from omni_core_rs import (
    PyGlobalEventBus,
    topic_file_changed,
    topic_file_created,
    topic_agent_step_complete,
)

# Check availability
if PyGlobalEventBus:
    # Publish event (fire-and-forget)
    PyGlobalEventBus.publish(
        "agent",                      # source
        "agent/step_complete",        # topic
        '{"thread_id": "sess-1"}'     # payload (JSON string)
    )

    # Get topic constants
    print(topic_file_changed())   # "file/changed"
    print(topic_file_created())   # "file/created"
```

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
from omni_core_rs import (
    scan_secrets,           # Secret scanning (regex-based)
    contains_secrets,       # Quick secret check
    scan_code_security,     # AST-based security scan (omni-ast)
    is_code_safe,           # Quick safety check
    scan_skill_tools,       # Skill tool discovery
    check_permission,       # Zero Trust permission check
    scan_paths,             # Virtual path skill scanning (no filesystem)
    parse_script_content,   # Parse single script content
)

# Security scanning
has_secrets, findings = scan_secrets(file_content)

# AST-based security scanning (omni-ast)
# Detects: forbidden imports, dangerous calls, suspicious patterns
is_safe, violations = scan_code_security(code)
# violations = [
#     {"rule_id": "SEC-IMPORT-001", "description": "...", "line": 5, "snippet": "import os"},
# ]

# Quick boolean check
if is_code_safe(code):
    print("Code passed security checks")

# Permission gatekeeper
allowed = check_permission("filesystem.read_file", ["filesystem:*", "git:status"])

# Virtual Path Scanning (Testing & API Support)
# Scan Python files without filesystem access - useful for testing
files = [
    ("/virtual/skill/scripts/tool_a.py", '''
@skill_command(name="tool_a")
def tool_a(param: str) -> str:
    """Tool A implementation."""
    return param
'''),
    ("/virtual/skill/scripts/tool_b.py", '''
@skill_command(name="tool_b")
def tool_b(value: int) -> int:
    """Tool B implementation."""
    return value * 2
'''),
]

# Scan virtual files with keywords and intents
tools = scan_paths(files, "test_skill", ["test"], ["testing"])
# Returns: [PyToolRecord(tool_name="test_skill.tool_a", ...), ...]

# Parse single script content directly
content = '''
@skill_command(name="my_tool")
def my_tool(param: str) -> str:
    """My tool description."""
    return param
'''
tools = parse_script_content(content, "/virtual/path.py", "test", [], [])
```

#### Virtual Path Scanning

The `scan_paths` and `parse_script_content` functions enable skill tool scanning without filesystem access:

| Function                                                                  | Purpose                     | Use Case                       |
| ------------------------------------------------------------------------- | --------------------------- | ------------------------------ |
| `scan_paths(files, skill_name, keywords, intents)`                        | Scan multiple virtual files | Batch testing, API integration |
| `parse_script_content(content, file_path, skill_name, keywords, intents)` | Parse single content        | Unit testing, content from DB  |

**Key Features:**

- No filesystem I/O - all content provided as strings
- Supports `skill_keywords` and `skill_intents` for metadata enrichment
- File hash computed for change detection
- Skips `__init__.py` and private files (starting with `_`)
- Returns `PyToolRecord` objects compatible with `scan_skill_tools`

### Immune System (Security + Sandbox)

```python
from omni.foundation.bridge.rust_immune import (
    RustImmuneBridge,
    scan_code_security,
    is_code_safe,
    run_sandbox,
    is_rust_available,
)

# Check if Rust core is available
if is_rust_available():
    print("Rust core loaded - immune system active")

# Level 1: Static Analysis
is_safe, violations = scan_code_security(source_code)
if not is_safe:
    print(f"Security violations: {len(violations)}")

# Level 2: Sandbox Execution (Docker/NsJail)
result = run_sandbox("/path/to/test_script.py")
# result = {
#     "success": True,
#     "exit_code": 0,
#     "stdout": "TEST_PASSED",
#     "stderr": "",
#     "duration_ms": 150,
# }
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
results = store.search_optimized(
    "skills",
    query_vector,
    5,
    '{"where_filter":"{\\"name\\":\\"git.commit\\"}","batch_size":1024}',
)
```

`PyVectorStore.search` (legacy) has been removed. Use `search_optimized(...)` or `search_tools(...)`.
Scanner options contract: `docs/reference/vector-search-options-contract.md`.

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
- `packages/rust/bindings/python/src/events.rs` (Event Bus)
- `packages/rust/bindings/python/src/io.rs`
- `packages/rust/bindings/python/src/sniffer.rs`
- `packages/rust/bindings/python/src/scanner.rs`
- `packages/rust/bindings/python/src/security.rs` (Immune System)
- `packages/rust/bindings/python/src/vector.rs`

**Rust Crates:**

- `packages/rust/crates/omni-events/` (Global Event Bus)
- `packages/rust/crates/omni-ast/` (Security Scanner)
- `packages/rust/crates/omni-sniffer/`
- `packages/rust/crates/omni-io/`
- `packages/rust/crates/omni-tags/`
- `packages/rust/crates/omni-edit/`
- `packages/rust/crates/omni-security/` (Sandbox)
- `packages/rust/crates/omni-vector/`

**Python Bridge:**

- `packages/python/foundation/src/omni/foundation/bridge/rust_immune.py`
- `packages/python/agent/src/omni/agent/core/evolution/immune/`
