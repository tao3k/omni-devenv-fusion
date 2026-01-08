---
name: "advanced_search"
version: "1.0.0"
description: "High-performance code search using ripgrep with structured results."
routing_keywords:
  [
    "search",
    "grep",
    "find",
    "ripgrep",
    "code search",
    "pattern",
    "regex",
    "replace",
    "match",
    "content",
    "text search",
  ]
authors: ["omni-dev-fusion"]
---

# Advanced Search Skill System Prompts

When using the Advanced Search skill, follow these patterns for effective code searching.

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

### Finding Decorators

```
pattern: @\w+
file_type: py
context_lines: 2
```

Finds decorator usage with context.

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

For structural code queries (not just text), use the `ast_search` tool instead:

- Pattern: "function_call($ARGS)" finds calls, not just text
- Language-aware matching
- Refactoring-safe (won't match strings/comments)

## Best Practices

1. Start with broad search, narrow with results
2. Use context_lines to understand matches
3. Check stats.elapsed_ms - if high, add filters
4. Combine with read_file for full context
