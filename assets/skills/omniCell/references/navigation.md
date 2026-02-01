# sys_query - Precision Code Extraction

Extract code elements from files using AST patterns. Part of **Project Cerebellum** for high-precision context management.

## Overview

`sys_query` provides **semantic-level code extraction** using `ast-grep` patterns. Unlike regex or line-based search, it understands code structure:

- Extract functions, classes, variables by their AST definition
- Get precise line numbers and byte offsets
- Filter by capture groups (e.g., function names only)
- Support for 23+ programming languages

## Usage

```python
from omni.core.skills.runtime.omni_cell import sys_query

# Extract all Python function definitions
result = await sys_query({
    "path": "src/main.py",
    "pattern": "def $NAME",
    "language": "python",
    "captures": ["NAME"]
})

if result.success:
    for item in result.items:
        print(f"Function: {item['captures']['NAME']} at line {item['line_start']}")
```

## Parameters

| Field      | Type         | Required | Description                                  |
| ---------- | ------------ | -------- | -------------------------------------------- |
| `path`     | string       | Yes      | File path to extract from                    |
| `pattern`  | string       | Yes      | ast-grep pattern (e.g., `"def $NAME"`)       |
| `language` | string       | No       | Language hint (auto-detected from extension) |
| `captures` | list[string] | No       | Capture names to include in results          |

## ast-grep Patterns

### Python

| Pattern                 | Description          |
| ----------------------- | -------------------- |
| `def $NAME`             | Function definitions |
| `class $NAME`           | Class definitions    |
| `$NAME = $VALUE`        | Variable assignments |
| `@$DECORATOR def $NAME` | Decorated functions  |
| `for $VAR in $ITER`     | For loops            |

### Rust

| Pattern              | Description          |
| -------------------- | -------------------- |
| `fn $NAME`           | Function definitions |
| `struct $NAME`       | Struct definitions   |
| `impl $NAME`         | Impl blocks          |
| `let $NAME = $VALUE` | Variable bindings    |

### JavaScript/TypeScript

| Pattern                | Description           |
| ---------------------- | --------------------- |
| `function $NAME`       | Function declarations |
| `const $NAME = $VALUE` | Const declarations    |
| `class $NAME`          | Class definitions     |
| `export $DECL`         | Export declarations   |

## Response Format

```json
{
  "success": true,
  "items": [
    {
      "text": "def hello(name: str) -> str:",
      "start": 120,
      "end": 156,
      "line_start": 10,
      "line_end": 11,
      "captures": {
        "NAME": "hello"
      }
    }
  ],
  "count": 1
}
```

### Response Fields

| Field        | Type    | Description                   |
| ------------ | ------- | ----------------------------- |
| `text`       | string  | Matched code text             |
| `start`      | integer | Byte offset start             |
| `end`        | integer | Byte offset end               |
| `line_start` | integer | Line number start (1-indexed) |
| `line_end`   | integer | Line number end (1-indexed)   |
| `captures`   | dict    | Captured variable values      |

## Examples

### Extract all functions from Python file

```python
result = await sys_query({
    "path": "src/utils.py",
    "pattern": "def $NAME($ARGS)",
    "captures": ["NAME", "ARGS"]
})
```

### Find all class definitions

```python
result = await sys_query({
    "path": "src/models.py",
    "pattern": "class $NAME"
})
```

### Extract with specific language

```python
result = await sys_query({
    "path": "src/main.rs",
    "pattern": "fn $NAME",
    "language": "rust",
    "captures": ["NAME"]
})
```

### Extract variables with type annotations (Python 3.9+)

```python
result = await sys_query({
    "path": "src/config.py",
    "pattern": "$NAME: $TYPE = $VALUE"
})
```

## Supported Languages

Python, Rust, JavaScript, TypeScript, Bash, Go, Java, C, C++, C#, Ruby, Swift, Kotlin, Lua, PHP, JSON, YAML, TOML, Markdown, Dockerfile, HTML, CSS, SQL

## Error Handling

```python
result = await sys_query({
    "path": "nonexistent.py",
    "pattern": "def $NAME"
})

if not result.success:
    print(f"Error: {result.error}")
```

## Comparison with Other Approaches

| Method         | Precision  | Speed     | Context Size |
| -------------- | ---------- | --------- | ------------ |
| `sys_query`    | AST-aware  | Fast      | Minimal      |
| `grep` / `rg`  | Text-based | Very Fast | Variable     |
| Full file read | N/A        | Fastest   | Full file    |

`sys_query` is ideal when you need:

- Precise code element extraction
- Function/class/variable definitions
- Minimal context for LLM prompts
- Multi-language codebases
