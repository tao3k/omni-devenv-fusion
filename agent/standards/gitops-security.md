# GitOps Security Guidelines: Path Safety

> **Core Principle**: All operations must stay within the Git toplevel (project root). Never access paths outside the project.

---

## 1. Path Safety Rule

**Fundamental**: All file operations must be bounded by `get_project_root()`.

```python
# ❌ WRONG: Path outside git toplevel
Path("/Users/guangtao/.claude/projects/some-file.txt")
Path("~/.claude/settings.json")

# ✅ CORRECT: Path within git toplevel
get_project_root() / ".claude" / "settings.json"
Path("agent/skills/git/tools.py")
```

---

## 2. Use Project-Root Utilities

Always use gitops utilities for path operations:

```python
from common.mcp_core.gitops import (
    get_project_root,
    get_spec_dir,
    get_instructions_dir,
    get_docs_dir,
    get_agent_dir,
    get_src_dir
)
```

| Purpose         | Function                 |
| --------------- | ------------------------ |
| Project root    | `get_project_root()`     |
| Specs directory | `get_spec_dir()`         |
| Instructions    | `get_instructions_dir()` |
| Documentation   | `get_docs_dir()`         |
| Agent source    | `get_agent_dir()`        |
| Source code     | `get_src_dir()`          |

---

## 3. Security Checklist

- [ ] All paths are relative or use `get_project_root()`
- [ ] No hardcoded `/Users/`, `/home/`, `/var/`
- [ ] No `Path.expanduser()` or `Path.home()`
- [ ] All operations bounded by git toplevel
