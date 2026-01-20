# Rust Crates for Omni-Dev-Fusion Fusion

> Rust Workspace - Now managed from project root `Cargo.toml`

This directory contains Rust crates for the Omni project. The workspace is now managed from the **project root** (`omni-dev-fusion/Cargo.toml`).

## Quick Start

```bash
# Build all crates from project root
cd omni-dev-fusion
cargo build

# Run tests
cargo test -p omni-sniffer
cargo test -p omni-types

# Build Python bindings
maturin develop -m packages/rust/bindings/python/Cargo.toml
```

## Crates

| Crate          | Purpose                              | Type    |
| -------------- | ------------------------------------ | ------- |
| `omni-types`   | Common type definitions, error types | Library |
| `omni-sniffer` | High-performance environment sensing | Library |
| `omni-core-rs` | Python bindings (PyO3)               | cdylib  |

## Directory Structure

```
packages/rust/
├── crates/
│   ├── omni-types/
│   │   ├── Cargo.toml    # Inherits from root workspace
│   │   └── src/
│   └── omni-sniffer/
│       ├── Cargo.toml    # Inherits from root workspace
│       └── src/
└── bindings/
    └── python/
        ├── Cargo.toml    # PyO3 bindings
        └── src/
```

## Python Binding Usage

```python
from omni_core_rs import PyOmniSniffer

sniffer = PyOmniSniffer(".")
snapshot = sniffer.get_snapshot()
print(snapshot.to_prompt_string())
```
