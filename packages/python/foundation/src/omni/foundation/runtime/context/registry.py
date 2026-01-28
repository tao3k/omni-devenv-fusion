"""
context/registry.py
Context registry for project-specific contexts.

Protocol-based design.

Manages registered language contexts and provides lookup.
"""

from __future__ import annotations

from .base import ProjectContext


class ContextRegistry:
    """Registry for project contexts.

    Manages registered language contexts and provides lookup.
    """

    _registry: dict[str, ProjectContext] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, context: ProjectContext) -> None:
        """Register a language context.

        Args:
            context: ProjectContext instance to register.
        """
        cls._registry[context.lang_id] = context

    @classmethod
    def get(cls, lang_id: str) -> ProjectContext | None:
        """Get context for a language.

        Args:
            lang_id: Language ID.

        Returns:
            ProjectContext or None if not found.
        """
        return cls._registry.get(lang_id)

    @classmethod
    def has(cls, lang_id: str) -> bool:
        """Check if context exists for a language.

        Args:
            lang_id: Language ID.

        Returns:
            True if context exists.
        """
        return lang_id in cls._registry

    @classmethod
    def list_languages(cls) -> list[str]:
        """List all registered language IDs.

        Returns:
            List of language IDs.
        """
        return list(cls._registry.keys())

    @classmethod
    def initialize_all(cls) -> None:
        """Initialize all registered contexts (for MCP server startup)."""
        if cls._initialized:
            return
        for context in cls._registry.values():
            context.get()  # Triggers lazy load
        cls._initialized = True


# =============================================================================
# Built-in Language Contexts
# =============================================================================


class PythonContext(ProjectContext):
    """Project context for Python development in this repo."""

    LANG_ID = "python"
    CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

    def _load_tooling(self) -> str:
        return """## 🛠️ Tooling (UV + Nix)

### Dependency Management (UV)
- **Primary**: Use `uv` for all Python dependency management
- **Commands**:
  - `uv add <package>` - Add dependency
  - `uv add --dev <package>` - Add dev dependency
  - `uv run python <script>` - Run script with project deps
  - `uv run pytest` - Run tests
  - `uv pip install` - Install dependencies

### Code Formatting (ruff)
- **Primary**: `ruff format` for Python formatting
- **Config**: pyproject.toml with ruff settings
- **Pre-commit**: `format-python` hook runs ruff format

### Type Hints (Mandatory)
```python
# ✅ Correct
def process_file(path: str, encoding: str = "utf-8") -> list[str]:
    ...

# ❌ Wrong: No type hints
def process_file(path, encoding="utf-8"):
    ...
```

### Imports (Explicit)
```python
# ✅ Correct: Explicit imports
from pathlib import Path
from typing import Dict, Any

# ❌ Wrong: Wildcard imports
from utils import *
```"""

    def _load_patterns(self) -> str:
        return """## 🔄 Common Patterns

### Singleton Pattern (for Caches)
```python
class MyCache:
    _instance: Optional["MyCache"] = None
    _loaded: bool = False

    def __new__(cls) -> "MyCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not MyCache._loaded:
            self._data = self._load()
            MyCache._loaded = True
```

### Lazy Loading
```python
def _ensure_loaded(self) -> T:
    # Thread-safe lazy loading with double-check locking
    if not self._loaded:
        with self._instance_lock:
            if not self._loaded:
                self._data = self._load()
                self._loaded = True
    return self._data
```

### Async Patterns
```python
# ✅ Correct: Async for I/O
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await client.get(url)

# ❌ Wrong: Blocking call in async
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

### Error Handling
```python
# ✅ Correct: Specific exceptions
try:
    result = await operation()
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    raise
```"""

    def _load_architecture(self) -> str:
        return """## 🏗️ Architecture (Skill-Centric OS)

### Core Components
- **packages/python/agent/src/omni/agent/**: MCP server entry point
- **assets/skills/**: Dynamic skill modules (Researcher, Git, etc.)

### Skill System
Skills are self-contained units with:
- `SKILL.md` - Skill metadata (frontmatter YAML)
- `scripts/*.py` - @skill_command decorated functions
- `README.md` - LLM guidance for the skill

### Skill Discovery
Skills are loaded from `assets/skills/` directory.
Use `omni skill list` to see available skills.

### Project Structure
```
omni-dev-fusion/
├── assets/skills/             # Skill modules
│   ├── researcher/
│   ├── git/
│   └── ...
├── packages/python/agent/     # MCP server implementation
└── packages/python/foundation/  # Shared library
```"""

    def _load_conventions(self) -> str:
        return """## 📏 Project Conventions

### File Naming
- **Skills**: `assets/skills/<skill_name>/` directory
- **Shared library**: `packages/python/foundation/src/omni/foundation/*.py`
- **Tests**: `packages/python/*/tests/**/*.py`

### Skill Structure
```
assets/skills/<skill_name>/
├── SKILL.md        # Skill metadata (frontmatter)
├── scripts/        # @skill_command functions
│   ├── __init__.py
│   └── commands.py
└── README.md       # LLM guidance
```

### Docstrings (Google-style)
```python
def calculate_metrics(values: list[float]) -> dict[str, float]:
    \"\"\"Calculate basic statistics from a list of values.

    Args:
        values: List of numeric values to process.

    Returns:
        Dictionary with mean, median, and std.
    \"\"\"
    ...
```

### Error Handling Rules
| Pattern | Why | Correct Alternative |
|---------|-----|---------------------|
| `except:` | Catches everything | `except ValueError:` |
| `list(dict.keys())` | Verbose | `list(dict)` |
| `type(x) == str` | Not duck-typed | `isinstance(x, str)` |
| Mutable default args | Shared state bug | `def f(x=None): if x is None: x=[]`

### Commit Conventions (Conventional Commits)
```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```"""


class NixContext(ProjectContext):
    """Project context for Nix/Devenv development."""

    LANG_ID = "nix"
    CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

    def _load_tooling(self) -> str:
        return """## 🛠️ Tooling (Nix + Devenv)

### Devenv Commands
- `devenv shell` - Enter development shell
- `devenv up` - Start devenv services
- `just test-mcp` - Run MCP server tests

### Nix Formatting
- Run `nix fmt` before committing
- Use `alejandra` for automatic formatting

### Pre-commit Hooks (Lefthook)
- `nixfmt` - Format Nix files
- `format-python` - Format Python files (ruff)
- `check-docs` - Lint docs (vale)
- `typos` - Spelling check
- `secrets` - Detect secrets"""

    def _load_patterns(self) -> str:
        return """## 🔄 Nix Patterns

### Nixago (Config Generation)
```nix
generators = [
  {
    name = "lefthook";
    gen = (config.omnibus.ops.mkNixago initConfigs.nixago-lefthook) {
      data = {
        commands = {
          "format-python".glob = "*.py";
          "format-python".run = "ruff format {staged_files}";
        };
      };
    } initConfigs.lefthook.nix initConfigs.lefthook.shell;
  }
];
```"""

    def _load_architecture(self) -> str:
        return """## 🏗️ Architecture

### Devenv Configuration
- `devenv.nix` - Main devenv config
- `units/modules/` - Nix modules
- `units/packages/` - Custom packages

### CI/CD (GitHub Actions)
- `.github/workflows/` - CI pipelines"""

    def _load_conventions(self) -> str:
        return """## 📏 Conventions

### Module Structure
```nix
{ inputs, config, lib, pkgs, ... }:
{
  imports = [ ];
  options = { };
  config = {
    services.postgres.enable = true;
    packages = [ pkgs.git ];
    env.GREET = "Hello";
  };
}
```"""


# Register built-in contexts
ContextRegistry.register(PythonContext())
ContextRegistry.register(NixContext())


__all__ = [
    "ContextRegistry",
    "NixContext",
    "PythonContext",
]
