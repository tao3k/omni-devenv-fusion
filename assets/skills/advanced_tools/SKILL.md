---
name: "advanced_tools"
version: "1.1.0"
description: "High-performance text search, file operations, and batch refactoring using Rust-based tools (ripgrep, fd, tree). Includes safe batch replacement with dry-run preview."
routing_keywords:
  [
    "search",
    "grep",
    "find",
    "ripgrep",
    "regex",
    "match",
    "content",
    "text",
    "advanced",
    "refactor",
    "replace",
    "batch",
    "tree",
    "directory",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Search code with regex"
  - "Find text in files"
  - "Find patterns in code"
  - "Count matches in codebase"
  - "Batch replace across files"
  - "Preview refactoring changes"
  - "View directory tree"
---

You have loaded the **Advanced Tools Skill**.

## Architecture

This skill provides three categories of tools:

| Category      | Tools                            | Use For                           |
| ------------- | -------------------------------- | --------------------------------- |
| **Search**    | `smart_search`, `smart_find`     | Fast text and file discovery      |
| **Visualize** | `tree_view`                      | Directory structure visualization |
| **Mutation**  | `regex_replace`, `batch_replace` | Safe text transformation          |

## What to Use Instead

| Task                        | Use Skill      | Tool                                       |
| --------------------------- | -------------- | ------------------------------------------ |
| Search code structure (AST) | **code_tools** | `search_code`, `search_directory`          |
| Code refactoring            | **code_tools** | `structural_replace`, `structural_preview` |
| File I/O                    | **filesystem** | `read_file`, `save_file`                   |
| Surgical file read          | **filesystem** | `read_file_context`                        |

## Key Differences

### Text Search (advanced_tools) vs AST Search (code_tools)

| Aspect          | advanced_tools (ripgrep)       | code_tools (AST)              |
| --------------- | ------------------------------ | ----------------------------- |
| **Search Type** | Text patterns                  | Code structure                |
| **Example**     | `class \w+` finds "class" text | `class $NAME` finds classes   |
| **Scope**       | Literal                        | Semantic                      |
| **Use Case**    | Finding text, TODO comments    | Refactoring, pattern matching |

### Single Replace vs Batch Replace

| Aspect       | `regex_replace` | `batch_replace`  |
| ------------ | --------------- | ---------------- |
| **Files**    | Single file     | Multiple files   |
| **Preview**  | No              | Yes (dry-run)    |
| **Safety**   | Manual review   | Automatic diff   |
| **Use Case** | One-off changes | Mass refactoring |

## Available Tools

### Search Commands

#### smart_search

Fast regex search using ripgrep with structured output.

```python
def smart_search(
    pattern: str,
    path: str = ".",
    file_type: str = None,
    context_lines: int = 2,
    max_results: int = 50,
) -> dict[str, Any]
```

#### smart_find

Fast file finding using fd with pattern matching.

```python
def smart_find(
    pattern: str = ".",
    path: str = ".",
    extension: str = None,
    max_results: int = 100,
) -> dict[str, Any]
```

### Visualization Commands

#### tree_view

Directory tree visualization (requires `tree` command).

```python
def tree_view(
    path: str = ".",
    depth: int = 3,
    ignore_hidden: bool = True,
) -> dict[str, Any]
```

### Mutation Commands

#### regex_replace

Single file regex replacement using sed.

```python
def regex_replace(
    file_path: str,
    pattern: str,
    replacement: str,
) -> dict[str, Any]
```

#### batch_replace

**Batch refactoring with dry-run safety** (RECOMMENDED for refactoring).

```python
def batch_replace(
    pattern: str,
    replacement: str,
    file_glob: str = "**/*",
    dry_run: bool = True,  # Safety: default is preview
    max_files: int = 50,
) -> dict[str, Any]
```

## Common Patterns

### Finding Function Definitions

```
pattern: def \w+
file_type: py
```

### Finding TODO Comments

```
pattern: TODO|FIXME|HACK
context_lines: 1
```

### Batch Refactoring (Safe)

```python
# Step 1: Preview changes
result = batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=True,  # Preview mode
)

# Step 2: Review diffs
for change in result["changes"]:
    print(change["diff"])

# Step 3: Apply if满意
result = batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=False,  # Live mode
)
```

## References

- **[Scenario: Batch Refactoring](./references/scenario-batch-refactoring.md)** - Detailed guide for safe batch replacement

## Optimization Tips

1. **Use file_type/glob filters** - Restricts search to specific languages
2. **Narrow path scope** - Search specific directories, not whole repo
3. **Use context_lines sparingly** - More context = more output = more tokens
4. **Use specific regex** - `"def test_"` matches fewer than `"test"`
5. **Always dry-run first** - Use `dry_run=True` for batch_replace

## Best Practices

1. Start with broad search, narrow with results
2. Use context_lines to understand matches
3. Check `stats.elapsed_ms` - if high, add filters
4. For refactoring: always preview with dry-run before applying
5. Combine with read_file for full context
