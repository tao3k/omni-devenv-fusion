# Thread-Safe Instructions Loader: Python Fork-Safety Case Study

> Keywords: python, threading, deadlock, uv run, fork, multiprocessing, lazy-loading

## Problem

The initial implementation of `mcp_core.instructions` caused a deadlock when used with `uv run`:

```bash
timeout 5 uv run python -c "from mcp_core.instructions import get_instructions"
# Hangs indefinitely
```

## Root Cause Analysis

1. **Eager Loading**: Module loaded instruction files at import time
2. **Lock Contention**: `threading.Lock()` was acquired during import
3. **Process Fork**: `uv run` spawns worker processes via fork
4. **Inherited Lock State**: Child inherits lock in locked state
5. **No Releasing Thread**: Child has no thread to release the lock
6. **Deadlock**: Child blocks forever waiting for unreachable lock

## Wrong Solution

Attempted boolean flag pattern:

```python
_locked = False
def _ensure_loaded():
    if _locked:
        return  # Race condition!
    _locked = True
    # ... load data ...
    _locked = False
```

### Why This Fails

- **Race Condition**: Thread A sets `_locked = True`, gets preempted
- Thread B sees `_locked = True`, returns early with empty `_data`
- Data inconsistency: Client receives empty instructions

## Correct Solution: Pure Lazy Loading + Double-Checked Locking

```python
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
instructions_dir = _PROJECT_ROOT / "agent" / "instructions"

_data: dict[str, str] = {}
_loaded: bool = False
_lock = threading.Lock()

def _ensure_loaded():
    # Fast path: Already loaded, no lock needed
    if _loaded:
        return
    # Slow path: Acquire lock and load
    with _lock:
        _load_data_internal()

def _load_data_internal():
    global _data, _loaded
    # Double-check after acquiring lock
    if _loaded:
        return
    # ... load files ...
    _data = loaded_data
    _loaded = True
```

## Why This Works

| Property | How It's Achieved |
|----------|-------------------|
| **Thread-Safe** | `with _lock:` ensures atomic check-and-set |
| **Fork-Safe** | No lock acquired at import time |
| **No Race** | Lock held during entire `_load_data_internal` |
| **Fast Path** | After first load, `_loaded=True` → no lock |
| **Correct Double-Check** | Lock acquires → recheck `_loaded` → load |

## Key Rules for Python Thread-Safety

1. **Never** call I/O or acquire locks at module level
2. **Always** use `with _lock:` for atomic operations
3. **Use** double-check pattern for performance
4. **Prefer** pure lazy loading to avoid fork deadlock

## Related Files

| File | Purpose |
|------|---------|
| `mcp-server/mcp_core/instructions.py` | Implementation |
| `mcp-server/tests/test_instructions.py` | 15 thread-safety tests |
| `agent/knowledge/threading-lock-deadlock.md` | Knowledge base entry |
| `docs/explanation/cache-patterns.md` | Cache patterns explanation |
