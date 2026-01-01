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

| Pattern | Why | Correct Alternative |
|---------|-----|---------------------|
| `import *` | Namespace pollution | Explicit imports |
| `except:` without type | Catches everything | `except ValueError:` |
| `list(dict.keys())` | Verbose | `list(dict)` |
| `type(x) == str` | Not duck-typed | `isinstance(x, str)` |
| Mutable default args | Shared state bug | `def f(x=None): if x is None: x=[]` |

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

## 4. Tool-Specific Notes

### 4.1 UV Usage
- Use `uv run python script.py` for scripts
- Use `uv run pytest` for tests
- Dependencies in `pyproject.toml`

### 4.2 MCP Server Pattern
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description."""
    return f"Result: {param}"
```

### 4.3 Testing
- Use `pytest` for unit tests
- MCP tool tests: Use `test_basic.py` pattern with `send_tool()`

### 4.4 Concurrency Patterns

#### Threading.Lock with Lazy Loading (Critical)

**Anti-Pattern: Eager Loading + Lock = Deadlock**
```python
# WRONG - Will deadlock in uv run / multiprocessing environments
import threading

_lock = threading.Lock()
_data = {}

def _ensure_loaded():
    with _lock:
        # Load data...

_ensure_loaded()  # <-- Eager loading at import time!
```

**Root Cause:**
1. Lock acquired during `import`
2. Process forks (uv run spawns workers)
3. Child inherits locked state but no thread to release it
4. Deadlock!

**Correct Pattern: Pure Lazy Loading + Double-Checked Locking**
```python
# CORRECT - Thread-safe and fork-safe
import threading

_data = {}
_loaded = False
_lock = threading.Lock()

def _ensure_loaded():
    # Fast path: No lock if already loaded
    if _loaded:
        return
    # Slow path: Acquire lock and load
    with _lock:
        _load_data_internal()

def _load_data_internal():
    global _data, _loaded
    if _loaded:
        return
    # Load data...
    _loaded = True

# NOTE: No eager loading! Deferred to first get_xxx() call.
```

**Key Rules:**
1. ❌ Never call `_ensure_loaded()` at module level
2. ✅ Use `with _lock:` for atomic operations
3. ✅ Double-check pattern for performance
4. ✅ Pure lazy loading avoids fork deadlock

#### Wrong Solution: Boolean Flag (Race Condition)
Using `_lock_locked = True/False` instead of Lock causes:
- Thread B returns empty data while Thread A is loading
- Race condition leads to `KeyError` or missing data

## 5. Related Documentation

| Document | Purpose |
|----------|---------|
| `design/writing-style/` | Writing standards |
| `mcp-server/tests/test_basic.py` | Test patterns |
| `pyproject.toml` | Project configuration |
