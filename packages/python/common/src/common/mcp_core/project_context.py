# mcp-core/project_context.py
"""
Project-Specific Context Framework

A framework for providing project-specific coding context.
Designed for extensibility - easy to add new languages and categories.

Uses GitOps via common.mcp_core.gitops for path detection.

Architecture:
- ProjectContext: Base class for language contexts
- ContextRegistry: Registry for all language contexts
- get_project_context(): Main API for retrieving context

Usage:
    # Register a new language context
    from mcp_core.project_context import ContextRegistry, ProjectContext

    class GoContext(ProjectContext):
        LANG_ID = "go"
        CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Go Tooling\n- Use `go mod` for dependencies..."

    ContextRegistry.register(GoContext())

    # Get context
    from mcp_core.project_context import get_project_context
    context = get_project_context("go", category="tooling")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar, Callable

# Project root detection using GitOps
from common.mcp_core.gitops import get_project_root

_PROJECT_ROOT: Path | None = None


def _get_project_root() -> Path:
    """Get the project root directory (uses GitOps)."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = get_project_root()
    return _PROJECT_ROOT


# =============================================================================
# Framework: Base Classes
# =============================================================================

T = TypeVar("T", bound="ProjectContext")


class ProjectContext(ABC):
    """Base class for project-specific language context.

    Subclass this to add support for a new language:

    class PythonContext(ProjectContext):
        LANG_ID = "python"
        CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Tooling\n- UV for dependency management..."

        def _load_patterns(self) -> str:
            return "## 🔄 Common Patterns\n- Singleton pattern..."

    ContextRegistry.register(PythonContext())
    """

    # Override these in subclass
    LANG_ID: str = ""
    CATEGORIES: list[str] = ["tooling"]

    def __init__(self) -> None:
        """Initialize context cache."""
        self._cache: dict[str, str] = {}
        self._loaded: bool = False

    def _ensure_loaded(self) -> None:
        """Lazy load all categories."""
        if self._loaded:
            return
        for cat in self.CATEGORIES:
            loader = getattr(self, f"_load_{cat}", lambda: "")
            self._cache[cat] = loader()
        self._loaded = True

    def get(self, category: str | None = None) -> str:
        """Get context for a category or all categories.

        Args:
            category: Specific category, or None for all.

        Returns:
            Context string.
        """
        self._ensure_loaded()
        if category:
            return self._cache.get(category, "")
        return "\n\n".join(self._cache.values())

    def has_category(self, category: str) -> bool:
        """Check if category exists.

        Args:
            category: Category name.

        Returns:
            True if category exists.
        """
        return category in self.CATEGORIES

    @property
    def lang_id(self) -> str:
        """Get language ID."""
        return self.LANG_ID

    @property
    def categories(self) -> list[str]:
        """Get all category names."""
        return self.CATEGORIES.copy()

    # Override these in subclass for each category
    def _load_tooling(self) -> str:
        """Load tooling context."""
        return ""

    def _load_patterns(self) -> str:
        """Load patterns context."""
        return ""

    def _load_architecture(self) -> str:
        """Load architecture context."""
        return ""

    def _load_conventions(self) -> str:
        """Load conventions context."""
        return ""


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
- **src/agent/main.py**: MCP server entry point
- **agent/skills/**: Dynamic skill modules (Software Engineering, Documentation, etc.)

### Skill System
Skills are self-contained units with:
- `manifest.json` - Skill metadata and dependencies
- `tools.py` - MCP tool implementations
- `guide.md` - LLM guidance for the skill
- `prompts.md` - Persona and behavior prompts

### Skill Discovery
```python
from agent.skills import SkillRegistry

# List all available skills
skills = SkillRegistry.list_skills()

# Load a skill
skill = SkillRegistry.load_skill("software_engineering")
```

### Shared Library (mcp_core)
- `mcp_core/execution.py` - Safe command execution
- `mcp_core/memory.py` - Project memory persistence
- `mcp_core/inference.py` - LLM inference client
- `mcp_core/lazy_cache.py` - Lazy-loading singleton caches
- `mcp_core/project_context.py` - Project-specific contexts (this!)
- `mcp_core/gitops.py` - Git workflow integration

### Project Structure
```
agent/
├── skills/                    # Skill modules
│   ├── software_engineering/  # The Architect skill (root)
│   ├── documentation/         # Scribe skill
│   └── ...
├── main.py                    # MCP server entry point
src/
├── mcp_server/                # MCP server implementation
└── common/
    └── mcp_core/              # Shared library
```"""

    def _load_conventions(self) -> str:
        return """## 📏 Project Conventions

### File Naming
- **Skills**: `agent/skills/<skill_name>/` directory
- **Shared library**: `mcp_core/*.py`
- **Tests**: `tests/test_*.py`
- **MCP tools**: One tool per function with `@mcp.tool()` decorator

### Skill Structure
```
agent/skills/<skill_name>/
├── manifest.json   # Skill metadata
├── tools.py        # MCP tool implementations
├── guide.md        # LLM guidance
└── prompts.md      # Persona prompts
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
| Mutable default args | Shared state bug | `def f(x=None): if x is None: x=[]` |

### Commit Conventions (Conventional Commits)
```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Scopes: nix, mcp, router, docs, cli, deps, ci
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


# =============================================================================
# Public API
# =============================================================================


def get_project_context(
    lang: str, category: str | None = None, include_builtins: bool = True
) -> str:
    """Get project-specific context for a language.

    This is the main API for retrieving project context.

    Args:
        lang: Language ID (python, nix, etc.)
        category: Optional category (tooling, patterns, architecture, conventions)
                 If None, returns all categories merged.
        include_builtins: Include built-in contexts (default: True)

    Returns:
        Project context string, or empty string if not found.

    Examples:
        # Get all Python context
        context = get_project_context("python")

        # Get specific category
        tooling = get_project_context("python", category="tooling")

        # Get with custom context
        context = get_project_context("go") + get_custom_context()
    """
    context = ContextRegistry.get(lang)
    if context is None:
        return ""
    return context.get(category)


def get_all_project_contexts() -> dict[str, dict[str, str]]:
    """Get all registered project contexts.

    Returns:
        Dictionary of lang_id -> {category -> content}.
    """
    result: dict[str, dict[str, str]] = {}
    for lang_id in ContextRegistry.list_languages():
        context = ContextRegistry.get(lang_id)
        if context:
            result[lang_id] = {cat: context.get(cat) for cat in context.categories}
    return result


def list_project_languages() -> list[str]:
    """List all registered language IDs.

    Returns:
        List of language IDs.
    """
    return ContextRegistry.list_languages()


def has_project_context(lang: str) -> bool:
    """Check if context exists for a language.

    Args:
        lang: Language ID.

    Returns:
        True if context exists.
    """
    return ContextRegistry.has(lang)


def register_project_context(context: ProjectContext) -> None:
    """Register a custom project context.

    Use this to add support for new languages:

    class GoContext(ProjectContext):
        LANG_ID = "go"
        CATEGORIES = ["tooling", "patterns", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Go Tooling..."

        def _load_patterns(self) -> str:
            return "## 🔄 Go Patterns..."

    register_project_context(GoContext())
    """
    ContextRegistry.register(context)


def initialize_project_contexts() -> None:
    """Initialize all project contexts (for MCP server startup).

    Call this at MCP server startup to pre-load all contexts.
    """
    ContextRegistry.initialize_all()


# Export
__all__ = [
    "ProjectContext",
    "ContextRegistry",
    "get_project_context",
    "get_all_project_contexts",
    "list_project_languages",
    "has_project_context",
    "register_project_context",
    "initialize_project_contexts",
    # Built-in contexts
    "PythonContext",
    "NixContext",
]
