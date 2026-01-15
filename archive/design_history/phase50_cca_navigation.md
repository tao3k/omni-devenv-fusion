# Phase 50: The Cartographer (CCA-Aligned Code Navigation)

> **Status**: Implemented
> **Date**: 2026-01-13
> **Alignment**: Meta Confucius Code Agent (CCA) Paper
> **Core Philosophy**: "Map over Territory" (AST-based)

## 1. Background & Vision

As the CCA paper states, the main bottleneck for handling large-scale codebases is **Context Window signal-to-noise ratio**, not LLM reasoning capability.

Current Agent behavior is like a junior programmer: to find a function definition, it opens the entire file (or multiple files) and reads everything. This causes:

1.  **Token Waste**: Reading 90% irrelevant implementation details
2.  **Attention Diffusion**: LLM gets lost in irrelevant code
3.  **Latency**: Both I/O and token generation have delays

**Phase 50 Goal**: Build **"The Cartographer"** - a Rust-based high-performance code navigation system that gives Agent **IDE-level** code awareness using **Abstract Syntax Trees (AST)** via `ast-grep`.

## 2. CCA Architecture Alignment

| CCA Concept               | Omni Implementation                                                                                              | Value                                                                         |
| :------------------------ | :--------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------- |
| **Agent Experience (AX)** | **Symbolic Outline**<br>Provides only class names, method signatures, docstrings; hides function bodies.         | Reduces token consumption by 10-50x, drastically improving "context density". |
| **Hierarchical Memory**   | **`omni-tags` (Rust Core)**<br>Memory-resident symbol index, serving as Agent's "long-term map".                 | Agent knows where symbols are without reading file content.                   |
| **Iterative Reasoning**   | **Navigation Loop**<br>Agent first views outline -> locates target -> only reads target function implementation. | Simulates human engineer's "go-to-definition" behavior, avoiding blind grep.  |

## 3. Architecture Overview

```
+-----------------------------------------------------------------------------+
|                          Phase 50: The Cartographer                         |
+-----------------------------------------------------------------------------+
|                                                                             |
|  Python Agent                                                               |
|       |                                                                     |
|       v                                                                     |
|  +---------------------------------------------------------------------+   |
|  |              omni-core-rs (PyO3 Bindings)                            |   |\
|  |                                                                       |   |
|  |   +-----------------+  +-----------------+  +---------------------+  |   |
|  |   | get_file_outline |  |  find_symbols   |  |  read_symbol_range  |  |   |
|  |   |  (Python/Rust)   |  |    (Search)     |  |   (Smart reading)   |  |   |
|  |   +--------+--------+  +--------+--------+  +----------+--------+  |   |
|  +-----------+-------------------+-------------------+----------+--------+   |
|              |                   |                   |                     |
|              v                   v                   v                     |
|  +---------------------------------------------------------------------+   |
|  |                    Rust Core Crates                                  |   |
|  |                                                                       |   |
|  |   +---------------------------------------------------------------+  |   |
|  |   |                       omni-tags                                |  |   |
|  |   |  +-----------------------------------------------------------+  |  |   |
|  |   |  |                    TagExtractor                          |  |  |   |
|  |   |  |  +--------------+  +--------------+  +--------------+     |  |  |   |
|  |   |  |  | ast-grep     |  | SgNode       |  |  Pattern     |     |  |  |   |
|  |   |  |  | (Core)       |  | (AST Node)   |  |  (Matcher)   |     |  |  |   |
|  |   |  |  +--------------+  +--------------+  +--------------+     |  |  |   |
|  |   |  +-----------------------------------------------------------+  |  |   |
|  |   |                                                               |  |   |
|  |   |  +-----------------------------------------------------------+  |  |   |
|  |   |  |                    Symbol struct                         |  |  |   |
|  |   |  |  name: String, kind: SymbolKind, line: usize, signature |  |  |   |
|  |   |  +-----------------------------------------------------------+  |  |   |
|  |   +---------------------------------------------------------------+  |   |
|  |                                                                       |   |
|  |   +---------------------------------------------------------------+  |   |
|  |   |                       omni-io                                   |  |   |
|  |   |  (Safe file reading with size limits & binary detection)       |  |   |
|  |   +---------------------------------------------------------------+  |   |
|  +---------------------------------------------------------------------+   |
|                                                                             |
+-----------------------------------------------------------------------------+
```

## 4. Technical Specification

### 4.1 Core Component: `crates/omni-tags` (Rust)

**Responsibilities:**

- Parse source code into AST using `ast-grep-core`.
- Extract symbols (Functions, Classes, Structs, Impls) using syntax-aware patterns.
- Robust handling of syntax errors and partial code.

**Why `ast-grep`?**

- **Accuracy**: Understands code structure, not just text patterns.
- **Robustness**: Handles multi-line definitions, decorators, and attributes correctly.
- **Extensibility**: Supports many languages via `tree-sitter`.

### 4.2 Supported Languages & Patterns

We use `ast-grep` patterns to extract symbols.

| Language   | Pattern (Concept)             | Kind     |
| ---------- | ----------------------------- | -------- |
| **Python** | `class $NAME: $$$`            | Class    |
| **Python** | `def $NAME($$$): $$$`         | Function |
| **Rust**   | `struct $NAME { $$$ }`        | Struct   |
| **Rust**   | `fn $NAME($$$) { $$$ }`       | Function |
| **TS/JS**  | `function $NAME($$$) { $$$ }` | Function |
| **TS/JS**  | `class $NAME { $$$ }`         | Class    |

### 4.3 Output Structure

```rust
#[derive(Debug, Clone, Serialize)]
pub struct Symbol {
    pub name: String,
    pub kind: SymbolKind, // Function, Class, Method, Struct, Trait, Impl
    pub line: usize,
    pub signature: String, // e.g. "def connect(self, timeout: int)"
}
```

## 5. Python API

### 5.1 PyO3 Bindings

```rust
// bindings/python/src/lib.rs

/// Generate a symbolic outline for a file.
#[pyfunction]
#[pyo3(signature = (path, language = "auto"))]
fn get_file_outline(path: String, language: Option<String>) -> String {
    // ...
}
```

### 5.2 Python Usage

```python
import omni_core_rs as core

# Generate outline for a Python file
outline = core.get_file_outline("src/agent/core/context_loader.py")
print(outline)
# Output:
# // OUTLINE: src/agent/core/context_loader.py
# L11     class ContextLoader
# L37     def __init__(self, max_file_size: int = DEFAULT_MAX_FILE_SIZE)
# ...
```

## 6. Implementation Plan

### Phase 50.1: Core Infrastructure

- [x] Create `omni-tags` crate structure
- [ ] Add `ast-grep-core` and `ast-grep-language` dependencies
- [ ] Implement `TagExtractor` with AST-based parsing
- [ ] Expose via PyO3 bindings

### Phase 50.2: Search & Navigation

- [ ] Implement `find_symbol` (project-wide search)
- [ ] Add `read_symbol_range` (smart range reading)
- [ ] Create `navigation` skill with tools
