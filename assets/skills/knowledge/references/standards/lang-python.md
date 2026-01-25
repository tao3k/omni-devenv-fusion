# Python Language Standards

> **Philosophy**: Readable, explicit, with type hints. Use `uv` for dependency management.

## 1. Core Principles

### 1.1 Type Hints (Mandatory)

All public functions must have type hints:

```python
# ✅ Correct
def process_file(path: str, encoding: str = "utf-8") -> list[str]:
    ...

# ❌ Wrong: No type hints
def process_file(path, encoding="utf-8"):
    ...
```

### 1.2 Explicit Imports

```python
# ✅ Correct: Explicit imports
from pathlib import Path
from typing import Dict, Any

# ❌ Wrong: Wildcard imports
from utils import *
```

### 1.3 Docstrings

Use Google-style docstrings:

```python
def calculate_metrics(values: list[float]) -> dict[str, float]:
    """Calculate basic statistics from a list of values.

    Args:
        values: List of numeric values to process.

    Returns:
        Dictionary with mean, median, and std.
    """
    ...
```

## 2. Forbidden Patterns (Anti-Patterns)

| Pattern                | Why                 | Correct Alternative                 |
| ---------------------- | ------------------- | ----------------------------------- |
| `import *`             | Namespace pollution | Explicit imports                    |
| `except:` without type | Catches everything  | `except ValueError:`                |
| `list(dict.keys())`    | Verbose             | `list(dict)`                        |
| `type(x) == str`       | Not duck-typed      | `isinstance(x, str)`                |
| Mutable default args   | Shared state bug    | `def f(x=None): if x is None: x=[]` |

## 3. Project Conventions

### 3.1 File Structure

```
mcp-server/
├── __init__.py        # Package marker
├── orchestrator.py    # Main MCP server
├── coder.py           # Coder MCP server
├── product_owner.py   # Feature lifecycle tools
└── tests/
    └── test_basic.py  # MCP tool tests
```

### 3.2 Async Patterns

```python
# ✅ Correct: Async for I/O operations
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await client.get(url)

# ❌ Wrong: Blocking call in async
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

### 3.3 Error Handling

```python
# ✅ Correct: Specific exceptions with context
try:
    result = await operation()
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    raise
```

## 4. UV Best Practices

### 4.1 Timeout Debugging Protocol

**The Timeout Anti-Pattern:**

```python
# ❌ Wrong: Running the same command multiple times
uv run python test.py
uv run python test.py
uv run python test.py  # Still failing? Try again!
# Trapped in endless test loop
```

**Correct Approach - Rule of Three:**

When a command times out **3 times**, execute error correction:

| Attempt | Action                       | Reason             |
| ------- | ---------------------------- | ------------------ | ------------------------ |
| 1       | Retry                        | Might be temporary |
| 2       | Check processes              | `ps aux            | grep python` for zombies |
| 3       | **Systematic investigation** | Start debugging    |

**Timeout Investigation Checklist:**

| Step | Action                                       |
| ---- | -------------------------------------------- | ------------ |
| 1    | Check for zombie processes: `ps aux          | grep python` |
| 2    | Check for file locks: `.pyc`, `__pycache__`  |
| 3    | Simplify test case: remove unrelated imports |
| 4    | Test in isolation: run file directly         |
| 5    | Check syntax: `python -m py_compile file.py` |
| 6    | Binary search imports: remove half at a time |

**Common Timeout Causes:**

| Cause                 | Solution                                         |
| --------------------- | ------------------------------------------------ |
| Process fork deadlock | See `agent/knowledge/threading-lock-deadlock.md` |
| Import cycle          | Refactor to break circular dependencies          |
| Infinite loop         | Add timeout, simplify logic                      |

### 4.2 Import Path Conflicts

**Symptom:**

```
ModuleNotFoundError: No module named 'module_name'
```

**Diagnosis:**

```bash
# Check where Python is looking
python3 -c "import sys; print(sys.path)"

# Find all module locations
find /project -name "module_name" -type d
```

**Solution: Workspace Configuration**

```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = ["mcp-server"]

[tool.uv.sources]
package_name = { workspace = true }
```

**Key insight:** `project.dependencies` must be PEP 508 compliant. Use `[tool.uv.sources]` for workspace packages.

### 4.3 Essential Debugging Commands

```bash
# Check for hanging processes
ps aux | grep python

# Kill stuck processes
pkill -9 -f "python.*mcp"

# Clear cache
find . -name "__pycache__" -exec rm -rf {} +

# Syntax check
python -m py_compile suspicious.py

# Test in isolation
cd module_dir && python -c "import module"
```

### 4.4 MCP Server Pattern

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description."""
    return f"Result: {param}"
```

### 4.5 Testing

- Use `pytest` for unit tests
- MCP tool tests: Use `test_basic.py` pattern with `send_tool()`

### 4.6 Troubleshooting

For Python-specific issues (threading, uv, concurrency), see:

- `agent/knowledge/threading-lock-deadlock.md`
- `agent/knowledge/uv-workspace-config.md`

## 5. Modern Python (3.12+)

For Python >= 3.12 specific standards including `StrEnum`, `match/case`, `@override`, and structured concurrency, see:

**[lang-python-modern.md](lang-python-modern.md)**

## 6. Related Documentation

| Document                         | Purpose                       |
| -------------------------------- | ----------------------------- |
| `lang-python-modern.md`          | Modern Python 3.12+ standards |
| `design/writing-style/`          | Writing standards             |
| `mcp-server/tests/test_basic.py` | Test patterns                 |
| `pyproject.toml`                 | Project configuration         |
