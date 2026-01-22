# Code Tools Skill

> Structural Code Intelligence - The Cartographer, The Hunter, and The Surgeon

Code analysis and refactoring skill powered by Rust AST engines (ast-grep, omni-edit).

---

## Overview

The `code_tools` skill provides three tiers of code intelligence:

| Tier             | Capability                   | Engine      | Use Case                  |
| ---------------- | ---------------------------- | ----------- | ------------------------- |
| **Cartographer** | Symbol extraction & outlines | `omni-tags` | Understand file structure |
| **Hunter**       | AST pattern search           | `omni-tags` | Find code semantically    |
| **Surgeon**      | Structural refactoring       | `omni-edit` | Modify code safely        |

---

## Commands

### Navigation (The Cartographer)

#### `outline_file`

Generate a symbolic skeleton of a source file.

```python
@omni("code_tools.outline_file", {"path": "src/agent.py", "language": "python"})
```

**Output:**

```text
// OUTLINE: src/agent.py
// Total symbols: 12
L15   [class]      Agent class Agent
L23   [method]     __init__ def __init__(self, name: str)
L45   [async_function] run async def run(self, task: str) -> None
L89   [function]   helper def helper(x: int) -> int
```

**Purpose:** 10-50x token reduction for LLM context

---

#### `list_symbols`

Extract structured symbol information.

```python
@omni("code_tools.list_symbols", {"file_path": "src/main.py"})
```

**Output:**

```json
[
  { "name": "Agent", "kind": "class", "line": 15, "signature": "class Agent:" },
  {
    "name": "__init__",
    "kind": "method",
    "line": 23,
    "signature": "def __init__(self, name: str)"
  },
  {
    "name": "run",
    "kind": "async_function",
    "line": 45,
    "signature": "async def run(self, task: str) -> None"
  }
]
```

---

#### `goto_definition`

Find where a symbol is defined.

```python
@omni("code_tools.goto_definition", {"symbol": "Kernel"})
```

**Output:**

```json
[
  {
    "file": "packages/python/core/src/omni/core/kernel/engine.py",
    "line": 42,
    "kind": "class",
    "signature": "class Kernel:"
  }
]
```

---

#### `find_references`

Find all usages of a symbol.

```python
@omni("code_tools.find_references", {"symbol": "connect"})
```

---

### Search (The Hunter)

#### `search_code`

Search AST patterns in a single file.

```python
@omni("code_tools.search_code", {
    "path": "src/client.py",
    "pattern": "connect($HOST, $PORT)",
    "language": "python"
})
```

**Pattern Syntax:**

| Pattern   | Meaning        | Example Match           |
| --------- | -------------- | ----------------------- |
| `$NAME`   | Any identifier | `foo`, `MyClass`        |
| `$ARGS`   | Argument list  | `(a, b, c)`             |
| `$PARAMS` | Parameter list | `(data, options)`       |
| `$$$`     | Variadic match | `(x, y, z)`             |
| `$$$ARGS` | Named variadic | `(host, port, timeout)` |

---

#### `search_directory`

Recursive AST search across directory.

```python
@omni("code_tools.search_directory", {
    "path": "src/",
    "pattern": "def $NAME($PARAMS)",
    "file_pattern": "**/*.py"
})
```

---

#### `ast_search`

Rust-powered AST search (alias for `search_code`).

```python
@omni("code_tools.ast_search", {
    "file_path": "src/main.py",
    "pattern": "class $NAME",
    "language": "python"
})
```

---

#### `ast_search_dir`

Rust-powered directory AST search.

```python
@omni("code_tools.ast_search_dir", {
    "path": "lib/",
    "pattern": "connect($$$ARGS)",
    "file_pattern": "**/*.py"
})
```

---

### Refactoring (The Surgeon)

#### `structural_replace`

Perform AST-based replacement on content.

```python
@omni("code_tools.structural_replace", {
    "content": "print(\"hello\")\nprint(\"world\")\n",
    "pattern": "print($$$ARGS)",
    "rewrite": "logger.info($$$ARGS)",
    "language": "python"
})
```

**Output:**

```text
// Replacements: 2

// Changes:
L1: "print(\"hello\")" -> "logger.info(\"hello\")"
L2: "print(\"world\")" -> "logger.info(\"world\")"

// Diff:
-print("hello")
-print("world")
+logger.info("hello")
+logger.info("world")
```

---

#### `structural_preview`

Preview changes without modifying files (dry-run).

```python
@omni("code_tools.structural_preview", {
    "file_path": "src/client.py",
    "pattern": "old_api($$$)",
    "rewrite": "new_api($$$)"
})
```

---

#### `structural_apply`

Apply structural refactoring to a file.

```python
@omni("code_tools.structural_apply", {
    "file_path": "src/client.py",
    "pattern": "print($$$ARGS)",
    "rewrite": "logger.info($$$ARGS)"
})
```

**Warning:** This modifies the file in place!

---

#### `refactor_repository`

Batch structural refactoring across codebase (The Ouroboros).

```python
# Dry run (safe)
@omni("code_tools.refactor_repository", {
    "root_path": "src/",
    "search_pattern": "print($$$ARGS)",
    "rewrite_pattern": "logger.info($$$ARGS)",
    "file_pattern": "**/*.py",
    "dry_run": true
})

# Apply changes (modifies files!)
@omni("code_tools.refactor_repository", {
    "root_path": "src/",
    "search_pattern": "deprecated_api($$$)",
    "rewrite_pattern": "new_api($$$)",
    "file_pattern": "**/*.py",
    "dry_run": false
})
```

---

### Analysis

#### `count_symbols`

Count symbols by kind in a file.

```python
@omni("code_tools.count_symbols", {"path": "src/agent.py"})
```

**Output:**

```json
{
  "total": 12,
  "by_kind": {
    "class": 2,
    "function": 5,
    "async_function": 3,
    "method": 2
  }
}
```

---

## Pattern Reference

### Python Patterns

| Pattern                    | Matches                    |
| -------------------------- | -------------------------- |
| `class $NAME`              | Class definitions          |
| `def $NAME($PARAMS)`       | Function definitions       |
| `async def $NAME($PARAMS)` | Async function definitions |
| `print($ARGS)`             | Print function calls       |
| `$VAR = $EXPR`             | Assignments                |

### Rust Patterns

| Pattern                 | Matches           |
| ----------------------- | ----------------- |
| `pub struct $NAME`      | Public structs    |
| `pub fn $NAME($PARAMS)` | Public functions  |
| `enum $NAME`            | Enum definitions  |
| `trait $NAME`           | Trait definitions |
| `impl $NAME`            | Impl blocks       |

### JavaScript/TypeScript Patterns

| Pattern                   | Matches               |
| ------------------------- | --------------------- |
| `class $NAME`             | Class definitions     |
| `function $NAME($PARAMS)` | Function definitions  |
| `interface $NAME`         | TypeScript interfaces |
| `$NAME($ARGS)`            | Function calls        |

---

## Workflows

### Code Understanding Workflow

```
1. outline_file()    → Get file skeleton
2. list_symbols()    → Extract structured symbols
3. search_code()     → Find specific patterns
4. goto_definition() → Navigate to definition
```

### Safe Refactoring Workflow

```
1. structural_preview()  → See what would change
2. Review diff output
3. structural_apply()    → Apply changes
4. Run tests
```

### Batch Refactoring Workflow

```
1. refactor_repository(dry_run=true)  → Preview all changes
2. Review statistics
3. refactor_repository(dry_run=false) → Apply all changes
4. Run tests
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    code_tools Skill                      │
│  assets/skills/code_tools/scripts/                       │
├─────────────────────────────────────────────────────────┤
│  navigation.py  │  analyze.py  │  refactor.py           │
│  (Cartographer) │  (Analysis)  │  (Surgeon)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Python Bindings (omni_core_rs)              │
│  packages/rust/bindings/python/src/                      │
│  navigation.rs  │  editor.rs  │  tags.rs                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Rust Core Engines                     │
├─────────────────────────────────────────────────────────┤
│  omni-tags/          │  omni-edit/                      │
│  - TagExtractor      │  - StructuralEditor              │
│  - Symbol extraction │  - BatchEditor                   │
│  - AST search        │  - Diff generation               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   ast-grep-core 0.40.5                   │
│  Tree-sitter parsers: Python, Rust, JavaScript, TS       │
└─────────────────────────────────────────────────────────┘
```

---

## Performance

| Operation                    | Time   | Notes                  |
| ---------------------------- | ------ | ---------------------- |
| Outline (1 file)             | ~3ms   | 10-50x token reduction |
| Search (1 file)              | ~5ms   | Semantic matching      |
| Search directory (100 files) | ~50ms  | Parallel scanning      |
| Batch refactor (100 files)   | ~100ms | With rayon parallelism |

---

## Files

| Path                                              | Purpose                       |
| ------------------------------------------------- | ----------------------------- |
| `assets/skills/code_tools/SKILL.md`               | Skill manifest                |
| `assets/skills/code_tools/scripts/navigation.py`  | Navigation commands           |
| `assets/skills/code_tools/scripts/analyze.py`     | Analysis commands             |
| `assets/skills/code_tools/scripts/refactor.py`    | Refactoring commands          |
| `packages/rust/crates/omni-tags/`                 | Symbol extraction engine      |
| `packages/rust/crates/omni-edit/`                 | Structural refactoring engine |
| `packages/rust/bindings/python/src/navigation.rs` | Navigation bindings           |
| `packages/rust/bindings/python/src/editor.rs`     | Editor bindings               |

---

## Related Documentation

- [AST-Based Code Navigation](ast-grep.md) - Deep dive into ast-grep patterns
- [Rust Crates](../architecture/rust-crates.md) - Rust crate reference
- [Skills Architecture](../architecture/skills.md) - Skill system overview
