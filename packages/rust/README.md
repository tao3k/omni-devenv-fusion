# Rust Crates for Omni-Dev-Fusion

> Rust Workspace - Managed from project root `Cargo.toml`

This directory contains Rust crates for the Omni project. The workspace is managed from the **project root** (`omni-dev-fusion/Cargo.toml`).

## Quick Start

```bash
# Build all crates from project root
cd omni-dev-fusion
cargo build

# Run tests
cargo test -p omni-sniffer
cargo test -p omni-vector

# Build Python bindings (from project root)
uv sync --reinstall-package omni-core-rs
```

## Crates

| Crate                  | Purpose                                                | Type    |
| ---------------------- | ------------------------------------------------------ | ------- |
| **Core Types**         |
| `omni-types`           | Common type definitions, error types                   | Library |
| **Code Analysis**      |
| `omni-ast`             | AST parsing and analysis                               | Library |
| `omni-sniffer`         | High-performance environment sensing                   | Library |
| `omni-tags`            | Tag extraction and management                          | Library |
| **Editor & Tools**     |
| `omni-edit`            | Code editing and batch operations (The Surgeon)        | Library |
| `omni-tokenizer`       | BPE tokenization                                       | Library |
| **Storage & Vector**   |
| `omni-vector`          | Vector store operations, tool indexing (The Librarian) | Library |
| `omni-lance`           | LanceDB integration                                    | Library |
| **Security & I/O**     |
| `omni-security`        | Security and sanitization (Hyper-Immune System)        | Library |
| `omni-io`              | Safe file I/O operations, context assembly             | Library |
| **Skills & Discovery** |
| `skills-scanner`       | Skill discovery and metadata scanning                  | Library |
| **Bindings**           |
| `omni-core-rs`         | Python bindings via PyO3                               | cdylib  |

## Directory Structure

```
packages/rust/
├── crates/
│   ├── omni-ast/           # AST parsing
│   ├── omni-edit/          # Code editing (The Surgeon)
│   ├── omni-io/            # Safe I/O, context assembly
│   ├── omni-lance/         # LanceDB integration
│   ├── omni-security/      # Security (Hyper-Immune)
│   ├── omni-sniffer/       # Environment sensing
│   ├── omni-tags/          # Tag extraction
│   ├── omni-tokenizer/     # BPE tokenization
│   ├── omni-types/         # Type definitions
│   ├── omni-vector/        # Vector store (The Librarian)
│   └── skills-scanner/     # Skill discovery
└── bindings/
    └── python/             # PyO3 bindings (omni-core-rs)
```

## Trinity Architecture

These crates power the **Trinity Architecture**:

- **The Librarian** (`omni-vector`): Vector store for semantic memory
- **The Surgeon** (`omni-edit`): AST-based code editing
- **Hyper-Immune System** (`omni-security`): Security and sanitization

## Python Binding Usage

```python
from omni_core_rs import PyVectorStore, PyOmniSniffer

# Vector store for semantic memory
store = PyVectorStore("./data/vectors", dimension=1536)

# Environment sensing
sniffer = PyOmniSniffer(".")
snapshot = sniffer.get_snapshot()
```
