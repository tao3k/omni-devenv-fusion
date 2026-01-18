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
uv add --package packages/python/common structlog     # Add to package
uv add --dev pytest pytest-asyncio                    # Dev dependency
uv sync                                              # Sync all
```

### 5.1 TOML Indentation Trap (Common Mistake)

**❌ Wrong: dependencies placed under wrong table**

```toml
[project]
name = "omni-dev-fusion-agent"
version = "0.3.0-dev"
requires-python = ">=3.12"

[project.scripts]
orchestrator = "agent.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent"]

[tool.uv.sources]
omni-dev-fusion-common = { workspace = true }

# ❌ WRONG! dependencies placed under [tool.hatch.build.targets.wheel]
[tool.hatch.build.targets.wheel]
dependencies = [
    "lancedb>=0.20.0",
    "structlog>=24.0.0",
]
```

**Result:** `uv sync` cannot recognize dependencies, structlog and other packages will NOT be installed.

**✅ Correct: dependencies under `[project]` table**

```toml
[project]
name = "omni-dev-fusion-agent"
version = "0.3.0-dev"
requires-python = ">=3.12"
# ✅ dependencies MUST be under [project] table
dependencies = [
    "lancedb>=0.20.0",
    "gitpython>=3.1.0",
    "langgraph>=1.0.5",
    "langsmith>=0.6.0",
    "libvcs>=0.14.0",
    "mcp>=1.1.0",
    "pydantic-ai>=1.39.0",
    "structlog>=24.0.0",
    "typer>=0.15.0",
    "omni-dev-fusion-common",
]

[project.scripts]
orchestrator = "agent.main:main"
omni = "agent.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent"]

[tool.uv.sources]
omni-dev-fusion-common = { workspace = true }
```

**After fix:**

```bash
uv sync
```

### 5.2 Adding Dependencies to Sub-packages

```bash
# Add dependency to specific sub-package
uv add --package packages/python/agent structlog
uv add --package packages/python/common anthropic

# Dev dependencies
uv add --dev --package packages/python/agent pytest pytest-asyncio
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
