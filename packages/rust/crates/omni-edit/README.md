# Omni Edit

> Structural Code Refactoring for Omni DevEnv.

## Overview

Omni Edit is a high-performance AST-based code modification library using ast-grep. Part of Phase 52: The Surgeon (CCA-Aligned Code Modification).

## Features

- AST-based code refactoring
- Structural search and replace
- Safe code transformations
- Multi-language support

## Usage

```rust
use omni_edit::StructuralEditor;

let editor = StructuralEditor::new();
let result = editor.replace_all(
    "fn $FN($ARGS) -> $RET { $BODY }",
    "pub $FN($ARGS) -> $RET { $BODY }",
    &content,
)?;
```

## Transformation Patterns

| Pattern              | Description                      |
| -------------------- | -------------------------------- |
| `structural_replace` | Replace all matches of a pattern |
| `structural_apply`   | Apply a single transformation    |
| `batch_refactor`     | Run multiple refactorings        |

## Architecture

See [docs/developer/ast-grep-core.md](../../../../docs/developer/ast-grep-core.md)

## License

Apache-2.0
