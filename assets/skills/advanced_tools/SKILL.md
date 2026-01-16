---
name: "advanced_tools"
version: "1.0.0"
description: "High-performance text search using ripgrep (rg). Replace for traditional grep/sed tools."
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
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Search code with regex"
  - "Find text in files"
  - "Find patterns in code"
  - "Count matches in codebase"
---

You have loaded the **Advanced Tools Skill**.

## Scope: Text Search ONLY

This skill provides **high-performance text search** using ripgrep (rg).

## What to Use Instead

| Task                        | Use Skill      | Tool                                       |
| --------------------------- | -------------- | ------------------------------------------ |
| Search code structure (AST) | **code_tools** | `search_code`, `search_directory`          |
| Code refactoring            | **code_tools** | `structural_replace`, `structural_preview` |
| File I/O                    | **filesystem** | `read_file`, `save_file`                   |

## Key Differences from code_tools (AST)

| Aspect          | advanced_tools (ripgrep)       | code_tools (AST)               |
| --------------- | ------------------------------ | ------------------------------ |
| **Search Type** | Text patterns                  | Code structure patterns        |
| **Example**     | `class \w+` finds "class" text | `class $NAME` finds classes    |
| **Scope**       | Literal (matches everything)   | Semantic (won't match strings) |
| **Use Case**    | Finding text, TODO comments    | Refactoring, pattern matching  |

## Available Tools

- `search_project_code`: Search regex patterns using ripgrep

## Common Patterns

### Finding Function Definitions

```
pattern: def $NAME
file_type: py
```

Finds all Python function definitions.

### Finding Classes

```
pattern: class $NAME
file_type: py
```

Finds all class definitions.

### Finding Imports

```
pattern: import $MODULE
file_type: py
```

Finds all import statements.

### Finding TODO Comments

```
pattern: TODO|FIXME|HACK
context_lines: 1
```

Finds all technical debt markers.

## Optimization Tips

1. **Use file_type filter** - Restricts search to specific languages
2. **Narrow path scope** - Search specific directories, not whole repo
3. **Use context_lines sparingly** - More context = more output = more tokens
4. **Use specific regex** - "def test\_" matches fewer than "test"

## Integration with AST Search

For structural code queries (not just text), use **code_tools** instead:

- Pattern: "function_call($ARGS)" finds calls, not just text
- Language-aware matching
- Refactoring-safe (won't match strings/comments)

## Best Practices

1. Start with broad search, narrow with results
2. Use context_lines to understand matches
3. Check stats.elapsed_ms - if high, add filters
4. Combine with read_file for full context
