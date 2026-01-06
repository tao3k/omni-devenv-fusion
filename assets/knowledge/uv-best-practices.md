# UV Best Practices

> Fast, reliable Python package management.

## 1. Import

```python
# ✅ Standard import (works in uv workspace)
from common.mcp_core.gitops import get_project_root
```

```python
# ❌ WRONG: No sys.path manipulation
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

## 2. Path Resolution

```python
# ✅ Use unified function
from common.mcp_core.gitops import get_project_root
PROJECT_ROOT = get_project_root()
```

```python
# ❌ WRONG: Manual parent traversal
PROJECT_ROOT = Path(__file__).resolve().parents[4]
```

## 3. Subprocess

```python
# ✅ uv run - handles environment
StdioServerParameters(command="uv", args=["run", "python", script])
```

```python
# ❌ WRONG: Manual PYTHONPATH injection
worker_env["PYTHONPATH"] = f"{server_root}:{current_path}"
```

## 4. Tests

```bash
# Run tests
uv run pytest
```

```python
# ❌ WRONG: Standalone Python script
python some_test.py
```

## 5. Dependencies

```bash
uv add --package src/common structlog     # Add to package
uv add --dev pytest pytest-asyncio       # Dev dependency
uv sync                                   # Sync all
```

## 6. Commands

```bash
uv run python src/script.py               # Run script
uv run pytest -k "test_swarm"             # Filter tests
uv run just validate                      # Run just task
```

## Related

- [UV Docs](https://docs.astral.sh/uv/)
- [Workspace Guide](https://docs.astral.sh/uv/concepts/projects/workspaces/)
