# Threading.Lock Deadlock in uv run

> Keywords: python, threading, deadlock, uv run, fork, multiprocessing

## Symptom

```bash
timeout 5 uv run python -c "import mcp_core"
# Hangs indefinitely
```

## Root Cause

1. Lock acquired during `import` (eager loading)
2. Process forks (uv run spawns workers)
3. Child inherits locked state but no thread to release it
4. Deadlock!

## Investigation Steps

```
1. Check processes: Found zombie Python processes
2. Clear __pycache__: Still hangs
3. Test in isolation: Works from mcp_core dir
4. Binary search imports: Hangs at 'import instructions'
5. Remove eager loading → WORKS!
```

## Wrong Solution (Race Condition)

```python
# WRONG: Boolean flag causes race condition
_locked = False
def _ensure_loaded():
    if _locked:
        return  # Thread B gets empty data!
    _locked = True
    # ... load data ...
    _locked = False
```

## Correct Solution: Pure Lazy Loading + Double-Checked Locking

```python
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
    # ... load files ...
    _data = loaded_data
    _loaded = True

# NOTE: No eager loading at import time!
```

## Key Rules

1. ❌ Never call `_ensure_loaded()` at module level
2. ✅ Use `with _lock:` for atomic operations
3. ✅ Double-check pattern for performance
4. ✅ Pure lazy loading avoids fork deadlock

## Related

- See: `agent/knowledge/uv-workspace-config.md`
- See: `mcp-server/mcp_core/instructions.py`
