---
name: code_tools
description: Use when searching code by structure or meaning, analyzing code patterns, finding class or function definitions, or exploring codebase architecture.
metadata:
  author: omni-dev-fusion
  version: "2.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/code_tools"
  routing_keywords:
    - "code"
    - "search"
    - "find"
    - "analyze"
    - "ast"
    - "pattern"
    - "class"
    - "function"
    - "structure"
    - "grep"
    - "semantic"
  intents:
    - "Search code by structure, meaning, or text"
    - "Analyze code for tools, decorators, patterns"
    - "Find class or function definitions"
    - "Explore codebase architecture"
---

# Code Tools Skill

You have loaded the **Code Tools Skill** - The unified entry point for all code operations.

## Primary Command

### `code_search` - Unified Search Interface

**This is the ONLY search tool you should use.**

```python
# Structure search (finds class/function definitions)
code_search("class User")
code_search("def authenticate")

# Semantic search (finds conceptually related code)
code_search("how does authentication work")
code_search("user validation logic")

# Text search (finds exact matches)
code_search("TODO: fix")
code_search("FIXME: memory leak")
```

Returns XML-formatted results optimized for LLM consumption.

## Search Strategy Selection

The tool automatically selects the best strategy:

| Query Type      | Strategy | Example                      |
| --------------- | -------- | ---------------------------- |
| `class Foo`     | AST      | Structural definition search |
| `def foo()`     | AST      | Function signature search    |
| Questions       | Vector   | Semantic/conceptual search   |
| `TODO`, `FIXME` | Grep     | Exact text match             |

## Workflow

```
1. SEARCH
   code_search("...")  # Unified entry point
   ↓
2. INTERPRET XML RESULTS
   - <item> for focused results
   - <search_interaction> for refinement suggestions
   ↓
3. REFINE (if needed)
   code_search("class ClassName")  # More specific
   ↓
4. READ FILE (for implementation details)
   read_file("path/to/file.py")
```

## Best Practices

1. **Always use `code_search`** for all code discovery tasks
2. **Be specific**: `code_search("class UserAuth")` > `code_search("auth")`
3. **Check XML guidance**: If results are too broad, the XML will suggest refinements
4. **Read files for details**: Use `read_file` after finding the right file

## Search Engines

| Engine | Use Case                   | Examples                  |
| ------ | -------------------------- | ------------------------- |
| AST    | Class/function definitions | `class Foo`, `def bar`    |
| Vector | Conceptual queries         | "how does auth work"      |
| Grep   | Exact text                 | `TODO`, `"error message"` |
