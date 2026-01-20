# Omni AST

> Unified AST Utilities using ast-grep.

## Overview

This crate provides a unified interface for AST-based code analysis across the Omni DevEnv project. Built on top of ast-grep for high-performance pattern matching.

## Features

- Multi-language AST support
- Pattern-based code search
- Syntax tree traversal
- Code transformation support

## Usage

```rust
use omni_ast::AstAnalyzer;

let analyzer = AstAnalyzer::new();
let ast = analyzer.parse("src/main.py")?;
let functions = analyzer.find_functions(&ast)?;
```

## Supported Languages

- Python
- Rust
- JavaScript/TypeScript
- Go
- Java

## License

Apache-2.0
