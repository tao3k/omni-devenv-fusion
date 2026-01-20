# ODF-REP: Rust Engineering Protocol

> **Version:** 1.1
> **Toolchain:** `nightly-2026-01-12`
> **Philosophy:** Atomic, Fearless, Zero-Cost.

This document defines the engineering standards for Rust core development in Omni-Dev-Fusion Fusion. All code commits under `packages/rust/` must pass this protocol review.

## 1. Architecture Principles

### 1.1 Atomicity

- **Single Responsibility:** Each crate must solve exactly one specific domain problem (e.g., `omni-sniffer` for sensing, `omni-git` for Git operations).
- **No Monoliths:** Strictly prohibit creating a "god crate" named `omni-core` containing all logic.
- **Dependency Tree:** Dependencies must be unidirectional and acyclic. Core crates (`crates/*`) must NOT depend on binding layers (`bindings/*`).

### 1.2 Core Separation

The Rust codebase is divided into two categories with clear boundaries:

| Category           | Path         | Responsibility                                         | Forbidden                                                               |
| :----------------- | :----------- | :----------------------------------------------------- | :---------------------------------------------------------------------- |
| **The Iron Heart** | `crates/*`   | Pure Rust business logic, algorithms, data structures. | **NO** `pyo3` or Python runtime dependencies. Must compile to WASM/CLI. |
| **The Glue**       | `bindings/*` | FFI interfaces, type conversion, GIL management.       | **NO** complex business logic. Only act as a搬运工 (porter).            |

### 1.3 Error Propagation

- **Library (Crates):** Must use `thiserror` to define explicit error enums (`enum Error`). **NEVER** use `anyhow` in library code (except in tests).
- **Boundary (Bindings):** At FFI boundaries, use `anyhow` to capture all errors and convert them uniformly to `PyErr` or host language exceptions.
- **Panic:** NEVER use `unwrap()` or `expect()` in production code. Must handle all `Result`.

## 2. Code Style & Nightly Features

### 2.1 Formatting

- All code must pass `cargo fmt`.
- Use `group_imports = "StdExternalCrate"` to keep imports tidy.

### 2.2 Nightly Feature Whitelist

Since we use Nightly, we can leverage cutting-edge features, but must be restrained. Allowed features:

- `#![feature(error_generic_member_access)]`: Provides better error context.
- `#![feature(lazy_cell)]`: Use std `LazyLock` instead of `once_cell`.
- `#![feature(portable_simd)]`: Use SIMD in compute-intensive modules like `omni-vector`.
- **PROHIBITED:** Any feature marked as `incomplete`.

### 2.3 Async Programming

- Unified use of `tokio` as Runtime.
- For CPU-intensive tasks (e.g., Git scanning), MUST use `tokio::task::spawn_blocking` or `rayon`. NEVER block async threads.

## 3. Performance Guidelines

### 3.1 Zero-Copy

- When transferring large data (file contents, large strings) from Python to Rust, MUST use `PyBuffer` or borrowing (`&str`) to avoid memory copying.
- Use `Cow<'a, str>` for strings that may be owned or borrowed.

### 3.2 Memory Layout

- Core data structures should derive `#[repr(C)]` if direct cross-language memory sharing is needed.
- Use `smallvec` or `tinyvec` to optimize small arrays on stack, reducing heap allocations.

## 4. Quality Assurance

### 4.1 Testing Hierarchy

- **Unit Tests:** Every `mod.rs` must contain `mod tests` at the bottom.
- **Doc Tests:** Public APIs MUST include doc tests (Example), ensuring docs are tested.
- **Integration Tests:** Simulate real call scenarios in `tests/` directory.

### 4.2 Linting

- CI must pass `cargo clippy -- -D warnings`.
- MUST enable `clippy::pedantic` and `allow` specific rules as needed based on project实际情况.

## 5. File Structure Specification

### 5.1 Workspace Structure

```
packages/rust/
├── crates/
│   ├── omni-types/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── lib.rs
│   └── omni-sniffer/
│       ├── Cargo.toml
│       └── src/
│           └── lib.rs
├── bindings/
│   └── python/
│       ├── Cargo.toml
│       ├── pyproject.toml
│       └── src/
│           └── lib.rs
├── rust-toolchain.toml    # Lock toolchain version
├── .clippy.toml           # Clippy strict configuration
└── .cargo/
    └── config.toml        # Platform-specific build configuration
```

### 5.2 Atomic Module Structure (Required for Crates > 300 LOC)

When a crate exceeds 300 lines of code, it MUST be split into atomic modules:

```
omni-edit/src/
├── lib.rs       # Thin re-export layer (< 100 lines)
├── error.rs     # Error enum (thiserror)
├── types.rs     # Data structures (Serialize/Deserialize)
├── [domain].rs  # Core business logic
└── [util].rs    # Helper utilities
```

**Rules:**

1. **lib.rs as Porter**: `lib.rs` MUST only contain:
   - Module declarations (`mod foo;`)
   - Public re-exports (`pub use foo::Bar;`)
   - Crate-level documentation

2. **One Concern Per Module**: Each module handles exactly one domain:
   - `error.rs` - Error types only
   - `types.rs` - Data structures only
   - `editor.rs` - Core logic only
   - `diff.rs` - Utility functions only

3. **Tests Collocated**: Each module contains its own `#[cfg(test)] mod tests`.

**Example (omni-edit):**

```rust
// lib.rs - Thin re-export layer
mod capture;
mod diff;
mod editor;
mod error;
mod types;

pub use editor::StructuralEditor;
pub use error::EditError;
pub use types::{EditConfig, EditLocation, EditResult};
```

```rust
// error.rs - Error types only
use thiserror::Error;

#[derive(Error, Debug)]
pub enum EditError {
    #[error("IO error: {0}")]
    Io(#[from] omni_io::IoError),
    // ...
}
```

```rust
// editor.rs - Core logic with tests
pub struct StructuralEditor;

impl StructuralEditor {
    pub fn replace(...) -> Result<EditResult, EditError> { ... }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_replace() { ... }
}
```

## 6. Naming Conventions

- **Crates:** `omni-*` prefix (kebab-case)
- **Modules:** `snake_case`
- **Traits:** `AdjectiveNoun` or `Verb` pattern (e.g., `Readable`, `Writable`)
- **Error Types:** `Error` suffix (e.g., `GitError`, `ScanError`)

## 7. Documentation Standards

Every public item MUST include `///` doc comments:

````rust
/// A high-performance Git repository scanner.
///
/// Uses libgit2 for O(1) branch lookups and efficient status scanning.
/// This crate is `no_std` compatible when compiled without the `git` feature.
///
/// # Example
///
/// ```rust,ignore
/// use omni_sniffer::OmniSniffer;
///
/// let sniffer = OmniSniffer::new("/path/to/repo");
/// let snapshot = sniffer.get_snapshot();
/// ```
pub struct OmniSniffer { ... }
````

## 8. Versioning & Release

- **SemVer:** Follow semantic versioning.
- **Changelog:** MUST update `CHANGELOG.md` on each release.
- **Workspace:** All crate versions are managed by root `Cargo.toml`'s `[workspace.package]`.
