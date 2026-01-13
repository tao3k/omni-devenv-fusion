---
name: "code_navigation"
version: "1.1.0"
description: "Navigate and search codebase structure using AST maps and patterns. Reduce context usage by 10-50x."
routing_keywords:
  [
    "structure",
    "outline",
    "map",
    "class",
    "function",
    "overview",
    "navigation",
    "symbols",
    "ast",
    "skeleton",
    "tree",
    "search",
    "find",
    "grep",
    "pattern",
    "hunt",
    "locate",
  ]
authors: ["omni-dev-fusion"]
---

You have loaded the **Code Navigation Skill** (Phase 50 & 51).

## Phase 50: The Cartographer - Code Navigation

This skill provides structural awareness of the codebase using AST-based parsing:

- **Map over Territory**: Generate symbolic outlines (50 tokens) instead of reading full content (5000 tokens)
- **AX Efficiency**: Reduce Agent's internal workspace usage by 10-50x
- **CCA-Aligned**: Confucius Code Agent philosophy - understand structure before diving into details

## Phase 51: The Hunter - Structural Code Search

Unlike naive grep, this skill searches for **CODE PATTERNS**, not strings:

- **Surgical Precision**: Find `connect($ARGS)` not every occurrence of "connect" in comments/strings
- **Semantic Matching**: Understands code structure (functions, classes, calls)
- **Variable Capture**: Extract matched parts with `$VAR` syntax

**Usage**:

- `outline_file`: Get high-level skeleton of any source file
- `search_code`: Search for AST patterns in a single file
- `search_directory`: Search for AST patterns across a directory

**Pattern Syntax**:

- `$NAME`: Capture any identifier
- `$ARGS`: Capture any argument list
- `$PARAMS`: Capture any parameter list
- `$EXPR`: Capture any expression

**Examples**:

```python
# Find all class definitions
search_code("src/", "class $NAME")

# Find all connect() calls
search_directory("lib/", "connect($ARGS)", "**/*.py")

# Find async function definitions
search_code(".", "async def $NAME($PARAMS)")
```

**Key Insights**:

- "A good map is worth a thousand lines of code."
- "Hunt with precision, not with a net."
