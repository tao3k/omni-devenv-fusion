# Omni Tags

> High-Performance Code Symbol Extraction for Omni DevEnv.

## Overview

Omni Tags provides AST-based symbol extraction using omni-ast (ast-grep). It enables fast code analysis for tags, symbols, and structural patterns.

## Features

- AST-based symbol extraction
- Syntax-aware matching for Python, Rust, Java, JavaScript
- Pattern-based code search
- Support for class, function, and variable extraction

## Usage

```rust
use omni_tags::{CodeTagger, TagExtractor};

let tagger = CodeTagger::new();
let tags = tagger.extract_tags("src/main.rs")?;

for tag in tags {
    println!("{}: {}", tag.name, tag.kind);
}
```

## Supported Languages

- Python (`.py`)
- Rust (`.rs`)
- JavaScript (`.js`, `.jsx`)
- TypeScript (`.ts`, `.tsx`)

## Patterns

Predefined patterns for common code structures:

| Pattern                | Description                 |
| ---------------------- | --------------------------- |
| `PYTHON_CLASS_PATTERN` | Python class definitions    |
| `PYTHON_DEF_PATTERN`   | Python function definitions |
| `RUST_STRUCT_PATTERN`  | Rust struct definitions     |
| `RUST_FN_PATTERN`      | Rust function definitions   |

## Architecture

See [docs/developer/ast-grep-core.md](../../../../docs/developer/ast-grep-core.md)

## License

Apache-2.0
