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

| Attempt | Action                       | Reason                                       |
| ------- | ---------------------------- | -------------------------------------------- |
| 1       | Retry                        | Might be temporary issue                     |
| 2       | Check processes              | `ps aux \| grep python` for zombie processes |
| 3       | **Systematic investigation** | Start problem solving workflow               |

**Must stop doing:**

- ❌ Continue repeating same command
- ❌ Assume "next time will succeed"
- ❌ Ignore logs and process states

**Must start doing:**

- ✅ Check for lingering processes
- ✅ Simplify test case
- ✅ Binary search for problematic module
- ✅ Document findings

### Timeout Investigation Checklist

When a command times out repeatedly:

| Step | Action                     | Why                                  |
| ---- | -------------------------- | ------------------------------------ |
| 1    | Check for zombie processes | `ps aux \| grep python`              |
| 2    | Check for file locks       | `.pyc`, `__pycache__`                |
| 3    | Simplify the test case     | Remove unrelated imports             |
| 4    | Test in isolation          | Run file directly, not via framework |
| 5    | Check syntax first         | `python -m py_compile file.py`       |
| 6    | Check imports one by one   | Binary search the problematic module |

### Common Timeout Causes

| Cause                 | Solution                                         |
| --------------------- | ------------------------------------------------ |
| Process fork deadlock | See `agent/knowledge/threading-lock-deadlock.md` |
| Import cycle          | Refactor to break circular dependencies          |
| Network timeout       | Check connectivity, increase timeout             |
| Infinite loop         | Add timeout, simplify logic                      |

### Knowledge Base

For language-specific issues, search the knowledge base:

```bash
# When you encounter a specific technical issue:
# 1. Identify keywords (e.g., "threading", "deadlock", "uv")
# 2. Search in agent/knowledge/
# 3. Read the corresponding .md file for solution

# Example: Python threading deadlock
See: agent/knowledge/threading-lock-deadlock.md

---

## Import Path Conflicts

### Symptom
```

ModuleNotFoundError: No module named 'module_name'

````

### Diagnosis
```bash
# Check where Python is looking
python3 -c "import sys; print(sys.path)"

# Find all module locations
find /project -name "module_name" -type d
````

### Solution: Workspace Configuration

```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = ["mcp-server"]

[tool.uv.sources]
package_name = { workspace = true }
```

**Key insight:** `project.dependencies` must be PEP 508 compliant. Use `[tool.uv.sources]` for workspace packages.

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
cd module_dir && python -c "import module"
```

---

## When to Ask for Help

- Timeout persists after 3 different investigation approaches
- Deadlock involving system resources (locks, threads, signals)
- Import path conflicts that `uv sync` doesn't resolve
- Language-specific issues → Search `agent/knowledge/`

---

_Document patterns. Break the loop._
