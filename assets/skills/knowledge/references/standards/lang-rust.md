# Rust Language Standards

> **Philosophy**: Memory safety, explicit error handling, cargo-first workflow.

## 1. Core Principles

### 1.1 Error Handling (Mandatory)

```rust
// ✅ Correct: Use Result/Option appropriately
fn parse_config(content: &str) -> Result<Config, ParseError> {
    serde_yaml::from_str(content).context("Failed to parse YAML")
}

// ❌ Wrong: Unhandled errors or unwrap
let config = serde_yaml::from_str(&content).unwrap();
```

### 1.2 Explicit Lifetimes

```rust
// ✅ Correct: Explicit when needed
fn process_string(s: &str) -> &str {
    s.trim()
}

// ❌ Wrong: Inferred lifetimes for complex cases
// Use explicit lifetimes when the compiler struggles
```

### 1.3 Ownership Clarity

```rust
// ✅ Correct: Clear ownership transfer
fn process_file(mut file: File) -> io::Result<File> {
    file.write_all(b"processed")?;
    Ok(file)
}

// Use &mut for in-place modification
```

## 2. Forbidden Patterns (Anti-Patterns)

| Pattern                   | Why                  | Correct Alternative       |
| ------------------------- | -------------------- | ------------------------- |
| `.unwrap()` in production | Panic risk           | `?` or `match`            |
| `clone()` without thought | Performance          | Borrow when possible      |
| `use std::io::*`          | Namespace pollution  | Specific imports          |
| `String` + `&str` mixing  | Allocation confusion | `format!()` or conversion |

## 3. Project Conventions

### 3.1 Crate Structure

```
crates/
├── core/           # Core functionality
├── cli/            # Command-line interface
└── api/            # Public API
```

### 3.2 Cargo Features

```toml
[features]
default = ["cli"]
cli = ["dep:clap"]
full = ["cli", "api"]
```

### 3.3 Documentation

````rust
/// Process the input configuration.
///
/// # Arguments
///
/// * `input` - Raw YAML string to parse
///
/// # Errors
///
/// Returns `ParseError` if YAML is invalid
///
/// # Examples
///
/// ```
/// let config = process_config("key: value");
/// ```
````

## 4. Tool-Specific Notes

### 4.1 Cargo Commands

- `cargo check` - Fast type checking
- `cargo build --release` - Production build
- `cargo test` - Run tests
- `cargo clippy` - Linting
- `cargo fmt` - Formatting

### 4.2 WASM Target (if applicable)

```toml
[target.wasm32-unknown-unknown]
runner = "wasm-server-runner"
```

### 4.3 Testing Strategy

- Unit tests in same file (`#[cfg(test)]` mod)
- Integration tests in `tests/`
- Doc tests in comments

## 5. Related Documentation

| Document              | Purpose              |
| --------------------- | -------------------- |
| `crates/*/Cargo.toml` | Crate configurations |
| `rust-toolchain.toml` | Toolchain version    |
