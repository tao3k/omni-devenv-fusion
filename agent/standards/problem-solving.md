# Problem Solving Guide

> Learn from debugging sessions. Document patterns to avoid repeated mistakes.

---

## Timeout Debugging Protocol

### The Timeout Anti-Pattern

**Wrong Approach:**
```python
# Running the same command multiple times hoping it will succeed
uv run python test.py
uv run python test.py
uv run python test.py  # Still failing? Try again!
# Trapped in endless test loop
```

**Correct Approach - Error Correction:**
```
1st timeout: "Might be temporary issue, retry"
2nd timeout: "Pattern detected! Stop repeating, start investigating"
3rd timeout: "Definite issue! Systematic debugging required"
```

### Rule of Three

When a command times out **3 times**, must execute error correction:

| Attempt | Action | Reason |
|---------|--------|--------|
| 1 | Retry | Might be temporary issue |
| 2 | Check processes | `ps aux \| grep python` for zombie processes |
| 3 | **Systematic investigation** | Start problem solving workflow |

**Must stop doing:**
- ❌ Continue repeating same command
- ❌ Assume "next time will succeed"
- ❌ Ignore logs and process states

**Must start doing:**
- ✅ Check for lingering processes
- ✅ Simplify test case
- ✅ Binary search for problematic module
- ✅ Document in `agent/standards/problem-solving.md`

### Timeout Investigation Checklist

When a command times out repeatedly:

| Step | Action | Why |
|------|--------|-----|
| 1 | Check for zombie processes | `ps aux \| grep python` |
| 2 | Check for file locks | `.pyc`, `__pycache__` |
| 3 | Simplify the test case | Remove unrelated imports |
| 4 | Test in isolation | Run file directly, not via uv run |
| 5 | Check syntax first | `python -m py_compile file.py` |
| 6 | Check imports one by one | Binary search the problematic module |

### Case Study: threading.Lock Deadlock

**Symptom:**
```
timeout 5 uv run python -c "import mcp_core"
# Hangs indefinitely
```

**Investigation:**
```
1. Checked processes: Found zombie Python processes
2. Cleared __pycache__: Still hangs
3. Tested in isolation: Works from mcp_core dir
4. Binary search imports: Hangs at 'import instructions'
5. Simplified instructions.py: Removed threading.Lock → WORKS!
```

**Root Cause:**
`threading.Lock()` at class level + eager loading in `__new__` caused deadlock in uv run's isolated environment.

**Solution:**
Replace Lock with simple boolean flag for single-threaded use case:
```python
# Before (problematic)
class Loader:
    _lock = threading.Lock()
    def __new__(cls):
        with cls._lock:  # Deadlock in uv run
            ...

# After (working)
_locked = False
def _ensure_loaded():
    global _locked
    if _locked:
        return
    _locked = True
    try:
        ...
    finally:
        _locked = False
```

**Lesson:**
> Threading primitives in module-level singletons with eager loading are high-risk. For single-threaded MCP server startup, simple boolean flags are safer.

---

## Import Path Conflicts

### Symptom
```
ModuleNotFoundError: No module named 'mcp_core'
```

### Diagnosis
```bash
# Check where Python is looking
python3 -c "import sys; print(sys.path)"

# Find all mcp_core locations
find /project -name "mcp_core" -type d
```

### Solution: Workspace Configuration

```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = ["mcp-server"]

[tool.uv.sources]
omni-orchestrator = { workspace = true }
```

**Key insight:** `project.dependencies` must be PEP 508 compliant (standard format). Use `[tool.uv.sources]` to tell uv where to find workspace packages.

---

## Debugging Commands

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
cd mcp_core && python -c "import module"
```

---

## When to Ask for Help

- Timeout persists after 3 different investigation approaches
- Deadlock involving system resources (locks, threads, signals)
- Import path conflicts that `uv sync` doesn't resolve

---

*Document patterns. Break the loop.*
