# UV Best Practices for Python Projects

> Keywords: uv, python, package management, workspace, dependencies

## Why UV?

UV is a modern Python package manager that is:

- **Fast**: Written in Rust, 10-100x faster than pip
- **Reliable**: Deterministic dependency resolution
- **Simple**: Single tool for virtualenv, pip, pip-tools, poetry

---

## 1. Project Structure

```
project/
├── pyproject.toml          # Project metadata & config
├── justfile                # Task runner
├── .gitignore
├── .cache/                 # Cache directory (gitignored)
│   └── chromadb/           # ChromaDB persistence
├── src/
│   ├── package_a/          # Workspace member
│   │   ├── __init__.py     # Required for package
│   │   └── pyproject.toml
│   ├── package_b/
│   │   ├── __init__.py
│   │   └── pyproject.toml
│   └── common/             # Shared utilities
│       ├── __init__.py     # Required for package
│       └── mcp_core/
│           ├── __init__.py
│           └── ...
└── tests/
```

### Key Rule: Always create `__init__.py`

```bash
# Creates a proper Python package
touch src/common/__init__.py
touch src/agent/__init__.py
```

---

## 2. pyproject.toml Configuration

### Root pyproject.toml

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = [
    "src/package_a",
    "src/package_b",
    "src/common",
]
```

### Package pyproject.toml (src/common/pyproject.toml)

```toml
[project]
name = "my-project-common"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "structlog>=24.0.0",
    "pydantic>=2.0.0",
]

[tool.uv.sources]
# Other workspace packages
my-project-agent = { workspace = true }
```

### Consuming Package (src/agent/pyproject.toml)

```toml
[project]
name = "my-project-agent"
requires-python = ">=3.12"

dependencies = [
    "my-project-common",  # Workspace dependency
    "mcp>=1.1.0",
]

[tool.uv.sources]
my-project-common = { workspace = true }
```

---

## 3. Import Patterns

### ✅ CORRECT: Direct imports in uv workspace

```python
# In any workspace package
from common.mcp_core.gitops import get_project_root
from agent.core.vector_store import get_vector_memory
```

### ❌ WRONG: Manual sys.path manipulation

```python
# WRONG: Don't do this
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "common"))
from mcp_core.gitops import get_project_root
```

### Why sys.path is bad

1. Fragile: Breaks if file moves
2. Non-standard: Not how Python packages work
3. Duplicate: UV workspace already handles this

---

## 4. Dependency Management

### Add dependency to specific package

```bash
uv add --package src/common structlog
```

### Add dev dependency

```bash
uv add --dev pytest pytest-asyncio
```

### Sync all packages

```bash
uv sync
```

### Lock all dependencies

```bash
uv lock
```

---

## 5. Running Commands

### Run Python

```bash
uv run python src/script.py
```

### Run with specific Python version

```bash
uv run --python 3.13 src/script.py
```

### Run pytest

```bash
uv run pytest
```

### Run just task

```bash
uv run just task-name
```

---

## 6. Cache Management

### Cache Location

Following prj-spec, cache goes in `.cache/` at git toplevel:

```
.gitignore:
/.cache/

Project root/
├── .cache/
│   ├── chromadb/     # Vector DB
│   └── tmp/          # Temp files
├── src/
└── pyproject.toml
```

### Get cache path

```python
from common.mcp_core.gitops import get_project_root

def get_cache_path() -> Path:
    project_root = get_project_root()
    return project_root / ".cache" / "my-app"
```

---

## 7. VSCode/IDE Setup

### .vscode/settings.json

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.extraPaths": ["./src"]
}
```

### LSP Configuration

UV projects work best with:

- Pyright or Pylance for type checking
- Ruff for formatting/linting

---

## 8. Common Patterns

### Pattern: Singleton with lazy import

```python
# common/core/singleton.py
from common.mcp_core.gitops import get_project_root

class MyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        project_root = get_project_root()
        # ... initialize
        self._initialized = True
```

### Pattern: Path resolution

```python
# CORRECT: Use get_project_root()
from common.mcp_core.gitops import get_project_root

def get_data_path() -> Path:
    return get_project_root() / "data"
```

---

## 9. Testing

### Test structure

```
tests/
├── conftest.py              # Pytest config
├── test_unit/
│   └── test_*.py
└── test_integration/
    └── test_*.py
```

### Run tests

```bash
uv run pytest tests/
```

### Test with coverage

```bash
uv run pytest --cov=src tests/
```

---

## 10. Publishing

### Build package

```bash
uv build
```

### Publish to PyPI

```bash
uv publish
```

---

## Related

- [UV Documentation](https://docs.astral.sh/uv/)
- [Pyproject.toml Spec](https://packaging.python.org/en/latest/specifications/pyproject-toml/)
- [UV Workspace Guide](https://docs.astral.sh/uv/concepts/projects/workspaces/)
