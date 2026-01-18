---
name: "code_tools"
version: "1.0.0"
description: "Code search, analysis, and refactoring using AST patterns. Search code structure, analyze modules, and refactor with precision. KEYWORDS: ast, syntax, parse, surgical, replace, transform, refactor, rename, symbol, class, function, method."
routing_keywords:
  [
    "code",
    "search",
    "find",
    "analyze",
    "refactor",
    "ast",
    "pattern",
    "class",
    "function",
    "structure",
    "outline",
    "rename",
    "edit",
    "transform",
    "tools",
    "decorators",
    "replace",
    "surgical",
    "syntax",
    "parse",
    "symbol",
  ]
authors: ["omni-dev-fusion"]
execution_mode: "library"
intents:
  - "Search code patterns using AST"
  - "Analyze code structure and decorators"
  - "Refactor and rename symbols"
  - "Find class or function definitions"
  - "Count symbols and lines in codebase"
---

You have loaded the **Code Tools Skill**.

## Scope: Code Search + Analysis + Refactoring

This skill provides **AST-based code operations** in three categories:

1. **Navigation**: Search and explore code structure
2. **Analysis**: Analyze code for tools, decorators, lines
3. **Refactoring**: Modify code with surgical precision

## Tool Categories

### Navigation (Read) - Search Code Structure

| Tool               | Description                            |
| ------------------ | -------------------------------------- |
| `outline_file`     | Get high-level skeleton of source file |
| `count_symbols`    | Count classes and functions in file    |
| `search_code`      | Search AST patterns in a single file   |
| `search_directory` | Search AST patterns across directory   |

### Analysis (Read) - Static Code Analysis

| Tool          | Description                    |
| ------------- | ------------------------------ |
| `find_tools`  | Find @tool decorated functions |
| `count_lines` | Count lines in a file          |

### Refactoring (Write) - Code Modification

| Tool                  | Description                         |
| --------------------- | ----------------------------------- |
| `structural_replace`  | Replace patterns in content strings |
| `structural_preview`  | Preview changes (dry-run)           |
| `structural_apply`    | Apply changes to a file             |
| `refactor_repository` | Mass refactoring across codebase    |

## What to Use Instead

| Task                 | Use Skill          | Tool                            |
| -------------------- | ------------------ | ------------------------------- |
| Text search in files | **advanced_tools** | `search_project_code` (ripgrep) |
| File I/O             | **filesystem**     | `read_file`, `save_file`        |

## Pattern Syntax (Navigation & Refactoring)

| Pattern   | Meaning               | Example Match     |
| --------- | --------------------- | ----------------- |
| `$NAME`   | Any single identifier | `foo`, `MyClass`  |
| `$ARGS`   | Any argument list     | `(a, b, c)`       |
| `$PARAMS` | Any parameter list    | `(data, options)` |
| `$EXPR`   | Any expression        | `x + y`           |
| `$$$`     | Variadic match        | `(a, b, c)`       |

### Refactoring-Specific Patterns

| Pattern        | Meaning                   | Example Match           |
| -------------- | ------------------------- | ----------------------- |
| `$$$`          | Variadic match (refactor) | `(host, port)`          |
| `$$$ARGS`      | Named variadic            | `(x, y, z)`             |
| `connect($$$)` | Function call with args   | `connect("host", 8080)` |
| `class $NAME`  | Class definition          | `class Agent:`          |

## Usage Examples

### Search Code Structure

```python
# Find all class definitions
search_code("src/", "class $NAME")

# Find all connect() calls
search_directory("lib/", "connect($ARGS)", "**/*.py")

# Get file outline
outline_file("src/client.py", "python")
```

### Analyze Code

```python
# Find @tool decorated functions
find_tools("src/agent/")

# Count lines in file
count_lines("README.md")
```

### Refactor Code (Preview First!)

```python
# Preview changes (safe - no modification)
structural_preview("src/client.py", "old_connect($$$)", "new_connect($$$)")

# Apply after confirming preview
structural_apply("src/client.py", "old_connect($$$)", "new_connect($$$)")
```

## Workflow

```
1. SEARCH/ANALYZE (Read)
   search_code() or find_tools()
   ↓
2. PREVIEW (For refactoring only)
   structural_preview(path, pattern, replacement)
   ↓
3. REVIEW
   - Check diff output
   - Verify matches are correct
   ↓
4. APPLY (Only for refactoring)
   structural_apply() or refactor_repository()
   ↓
5. VERIFY
   - Run tests
   - Review changes
```

## Best Practices

1. **Always Preview First**: Use `structural_preview` before `structural_apply`
2. **Use Specific Patterns**: `old_api($$$)` is better than `old_api`
3. **Navigation for Exploration**: Use `search_code` to understand structure before modifying
4. **Test Small Changes First**: Try on a single file before mass refactoring

## Key Insights

- "A good map is worth a thousand lines of code."
- "Hunt with precision, not with a net."
- "Preview twice, apply once."
- "AST patterns find code, not strings."
