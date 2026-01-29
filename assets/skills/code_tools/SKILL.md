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
permissions:
  - "filesystem:read_file"
  - "filesystem:list_dir"
  - "filesystem:search"
  - "knowledge:search"
---

You have loaded the **Code Tools Skill**.

## Scope: Code Search + Analysis + Refactoring

This skill provides **AST-based code operations** in three categories:

1. **Navigation**: Search and explore code structure
2. **Analysis**: Analyze code for tools, decorators, lines
3. **Refactoring**: Modify code with surgical precision

## Tool Categories

### Smart Exploration (Unified Interface)

| Tool               | Description                                       |
| ------------------ | ------------------------------------------------- |
| `smart_ast_search` | **PRIMARY SEARCH TOOL**. Handles patterns & rules |

### Navigation (View)

| Tool            | Description                            |
| --------------- | -------------------------------------- |
| `outline_file`  | Get high-level skeleton of source file |
| `count_symbols` | Count classes and functions in file    |
| `list_symbols`  | Get structured symbol list             |

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

| Pattern | Meaning               | Example Match    |
| ------- | --------------------- | ---------------- |
| `$NAME` | Any single identifier | `foo`, `MyClass` |
| `$$$`   | Variadic match        | `(a, b, c)`      |
| `$EXPR` | Any expression        | `x + y`          |

### Examples for `smart_ast_search`

1. **Semantic Intents (PREFERRED)**:
   - `query="classes"`: Find all class definitions.
   - `query="functions"`: Find all function definitions.
   - `query="methods"`: Find all method definitions.
   - `query="decorators"`: Find all decorated functions.

2. **AST Patterns**:
   - `query="class $NAME"`: Specific class search.
   - `query="def $NAME($$$)"`: Specific function search.
   - `query="connect($$$)"`: Function call with any arguments.

## Advanced YAML Rules (Power Search)

For complex searches that require multiple conditions or nested constraints, use `search_with_rules` with YAML syntax:

```yaml
rule:
  any:
    - pattern: "print($$$)"
    - pattern: "logger.info($$$)"
  inside:
    kind: function_definition
    has:
      field: name
      regex: "^test_"
```

_The above rule finds all print or logger.info calls that are inside function definitions starting with 'test\_'._

### Rule Key Concepts

- **rule**: The core matching logic
- **any/all/not**: Logical combinations of patterns
- **inside/has/follows**: Structural constraints based on relationship to other nodes
- **regex**: Regular expression matching for captured variables

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
