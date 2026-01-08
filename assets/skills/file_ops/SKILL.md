---
name: "file_ops"
version: "1.0.0"
description: "File operations including read, write, search, and AST-based refactoring."
routing_keywords:
  [
    "refactor",
    "rewrite",
    "ast",
    "edit file",
    "modify",
    "transform",
    "replace",
    "move",
    "rename",
    "refactoring",
  ]
authors: ["omni-dev-fusion"]
---

# File Operations Skill System Prompts

When using File Operations skill, follow these patterns for safe and effective file manipulation.

## Reading Files

### Basic Read

```python
await read_file(path="src/main.py")
```

Returns file with line numbers.

### Reading Specific Sections

1. Use read_file to get full content
2. Parse sections manually (no slice tool available)

### Large Files

- 100KB limit enforced
- For larger files, use search_files with patterns

## Writing Files

### Safe Write Pattern

```python
await save_file(
    path="src/new_module.py",
    content="# New module\n...",
    create_backup=True,
    validate_syntax=True,
    auto_check_writing=True
)
```

### Writing Markdown

- auto_check_writing runs polish_text automatically
- Violations returned as warnings
- Fix violations before committing

### Backup Behavior

- .bak file created for existing files
- Previous .bak overwritten on next write
- Manual cleanup required

## Searching Files

### Basic Search

```python
await search_files(pattern="TODO", path="src/")
```

Case-insensitive, 100 match limit.

### Regex Search

```python
await search_files(pattern=r"def \w+", path="src/", use_regex=True)
```

Full regex support with multiline matching.

## AST Operations

### ast_search Patterns

| Pattern           | Meaning           |
| ----------------- | ----------------- |
| `def $NAME`       | All functions     |
| `async def $NAME` | Async functions   |
| `if $COND:`       | If statements     |
| `print($ARGS)`    | Print calls       |
| `import $MODULE`  | Import statements |
| `class $NAME`     | Class definitions |

### ast_rewrite Patterns

```python
# Rename function
await ast_rewrite(
    pattern="def $NAME($ARGS):",
    replacement="async def $NAME($ARGS):",
    lang="py"
)

# Replace calls
await ast_rewrite(
    pattern="print($MSG)",
    replacement="logger.info($MSG)",
    lang="py"
)
```

### Safety for ast_rewrite

1. Creates backups automatically
2. Returns diff of changes
3. Use --dry-run if available (not in this skill)
4. Review changes before committing

## Common Patterns

### Find All Test Files

```python
await search_files(pattern="test_", path="src/", use_regex=True)
```

### Replace All print with logger

```python
await ast_rewrite(
    pattern="print($MSG)",
    replacement="logger.info($MSG)",
    lang="py"
)
```

### Add Type Hints

```python
await ast_rewrite(
    pattern="def $NAME($ARGS):  # TODO: type",
    replacement="def $NAME($ARGS) -> None:  # TODO: type",
    lang="py"
)
```
