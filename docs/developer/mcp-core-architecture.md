# mcp_core Architecture

> **Phase 30: Modular Architecture** | **Phase 31: Performance Optimization** | **Phase 32: Import Optimization**

Shared library providing common functionality for orchestrator and coder MCP servers.

## Overview

mcp_core is a modular, protocol-based design for type-safe, testable code with ODEP-aligned performance optimizations.

```
common/mcp_core/
├── protocols.py          # Protocol definitions (405 lines)
├── execution/            # Safe command execution
├── lazy_cache/           # Lazy-loading singleton caches
├── utils/                # Common utilities
├── context/              # Project-specific coding context
├── inference/            # LLM inference client
├── memory/               # Project memory persistence
├── api/                  # API key management
└── instructions/         # Project instructions loader
```

## Module Structure

### protocols.py

Protocol definitions for type-safe, testable code. All major components implement these protocols for mocking capability.

```python
from mcp_core.protocols import ISafeExecutor, IInferenceClient

# For testing, mock the protocol
from unittest.mock import MagicMock
mock_executor: ISafeExecutor = MagicMock()
```

**Available Protocols:**

- `ILazyCache` - Lazy-loading singleton caches
- `IFileCache` - File content caching
- `IConfigCache` - Configuration caching
- `ISettings` - Project settings management
- `ISafeExecutor` - Safe command execution
- `IInferenceClient` - LLM inference client
- `IProjectContext` - Project-specific context
- `IContextRegistry` - Context registry
- `IPathSafety` - Path safety checking
- `IEnvironmentLoader` - Environment variable loading
- `IMCPLogger` - Structured logging

### execution/

Safe command execution with security boundaries.

```python
from mcp_core.execution import SafeExecutor, check_dangerous_patterns, check_whitelist

# Check if command is safe
is_safe, error = check_dangerous_patterns("rm", ["-rf", "/"])
```

**Modules:**

- `executor.py` - SafeExecutor class
- `security.py` - Security utilities (Phase 31: pre-compiled regex)
- `protocols.py` - Execution protocols

**Phase 31 Optimization:** Regex patterns are pre-compiled at module load time, providing **70% faster** pattern matching.

### lazy_cache/

Lazy-loading singleton caches for protocols and configs.

```python
from mcp_core.lazy_cache import FileCache, ConfigCache, MarkdownCache

# First access triggers lazy load
config = ConfigCache()
content = config.get()  # Loads from file
```

**Modules:**

- `base.py` - LazyCacheBase class
- `file_cache.py` - File content caching
- `config_cache.py` - Configuration caching
- `markdown_cache.py` - Markdown content caching
- `repomix_cache.py` - Repomix output caching

### utils/

Common utilities including logging and path checking.

```python
from mcp_core.utils import setup_logging, is_safe_path, load_env_from_file

# Setup structured logging
logger = setup_logging("my_module")

# Check if path is safe
is_safe, error = is_safe_path("/path/to/file")
```

**Modules:**

- `logging.py` - Structured logging with structlog
- `path_safety.py` - Path safety checking
- `file_ops.py` - Safe file reading/writing
- `env.py` - Environment variable utilities

### context/

Project-specific coding context framework.

```python
from mcp_core.context import get_project_context, ContextRegistry, ProjectContext

# Get context for Python development
python_context = get_project_context("python")
python_context = get_project_context("python", category="tooling")
```

**Built-in Contexts:**

- `PythonContext` - Python development guidelines
- `NixContext` - Nix/Devenv development guidelines

**Categories:** tooling, patterns, architecture, conventions

### inference/

LLM inference client with persona support.

```python
from mcp_core.inference import InferenceClient, PERSONAS, build_persona_prompt

client = InferenceClient()
result = await client.complete(
    system_prompt=build_persona_prompt("architect"),
    user_query="Design a REST API..."
)
```

**Modules:**

- `client.py` - InferenceClient class
- `personas.py` - Persona definitions (architect, platform_expert, sre, etc.)
- `api.py` - API key loading

### memory/

Project memory persistence using ADR (Architectural Decision Records) pattern.

```python
from mcp_core.memory import ProjectMemory

memory = ProjectMemory()
memory.add_decision(title="ADR-Title", problem="...", solution="...")
decisions = memory.list_decisions()
```

**Features:**

- Architectural Decision Records (ADRs)
- Task tracking (backlog-md compatible)
- Context snapshots
- Active context management (The "RAM")
- Spec path management (Legislation Workflow)

### api/

API key management with multiple source support.

```python
from mcp_core.api import get_anthropic_api_key

api_key = get_anthropic_api_key()
```

**Priority:**

1. Environment variable (`ANTHROPIC_API_KEY`)
2. `.claude/settings.json`
3. `.mcp.json` (Claude Desktop format)

### instructions/

Eager-loaded project instructions.

```python
from mcp_core.instructions import get_instructions, get_instruction

# First call triggers lazy load
all_instructions = get_instructions()
guide = get_instruction("project-conventions")
```

## Settings (common.settings)

Settings uses a fast import path for performance:

```python
# Recommended (fastest - single module)
from common.settings import get_setting, Settings

# Also supported (backward compatible)
from mcp_core import get_setting
```

**Features:**

- Dot-notation access (`"config.cog_toml"`)
- Thread-safe singleton
- `--conf` flag support for custom config directory
- YAML with fallback to simple parsing

## Path Utilities (common.skills_path)

A centralized module for skill path handling (Phase 32):

```python
from common.skills_path import SKILLS_DIR, load_skill_module
from common.gitops import get_project_root

# Get base skills directory from settings.yaml
base = SKILLS_DIR()  # -> Path("assets/skills")

# Get skill directory
git_dir = SKILLS_DIR(skill="git")  # -> Path("assets/skills/git")

# Get skill file with keyword args
git_tools = SKILLS_DIR(skill="git", filename="tools.py")

# Get nested path (e.g., known_skills.json index)
known_skills = SKILLS_DIR(skill="skill", path="data/known_skills.json")

# Load skill module directly
git_tools = load_skill_module("git")
```

**Configuration** (`settings.yaml`):

```yaml
assets:
  skills_dir: "assets/skills" # Read by SKILLS_DIR
```

**Benefits:**

- Single source of truth for skills path
- GitOps-aware project root detection (via `git rev-parse --show-toplevel`)
- Replaces verbose `Path(__file__).resolve().parent.parent.parent` patterns
- Cached for performance

**Replaced Patterns:**

| Old Pattern                                                            | New Pattern                                    |
| ---------------------------------------------------------------------- | ---------------------------------------------- |
| `get_project_root() / get_setting("skills.path") / "git" / "tools.py"` | `SKILLS_DIR(skill="git", filename="tools.py")` |
| `importlib.util.spec_from_file_location(...)`                          | `load_skill_module("git")`                     |

## Import Guidelines

### For Fastest Import (Recommended)

```python
from common.settings import get_setting
from common.gitops import get_project_root
```

### For Protocol-Based Testing

```python
from mcp_core.protocols import ISafeExecutor, IInferenceClient
from mcp_core.execution import ISafeExecutor as ExecutionProtocol
```

### For Modular Components

```python
from mcp_core.execution import SafeExecutor
from mcp_core.context import get_project_context
from mcp_core.inference import InferenceClient
```

## Performance Optimizations

### Phase 32: Import Optimizations

**Key Optimizations:**

| Module                     | Before | After | Speedup  |
| -------------------------- | ------ | ----- | -------- |
| `agent.core.schema`        | 421ms  | 3.6ms | **117x** |
| `agent.core.skill_manager` | 200ms  | 3.5ms | **57x**  |
| `agent.core.bootstrap`     | 169ms  | 0.8ms | **211x** |
| `agent.mcp_server`         | 156ms  | 0.8ms | **195x** |

**Techniques Applied:**

1. **Lazy Logger Initialization**

   ```python
   # Before: Eager import
   import structlog
   logger = structlog.get_logger(__name__)

   # After: Lazy initialization
   _cached_logger = None

   def _get_logger():
       global _cached_logger
       if _cached_logger is None:
           import structlog
           _cached_logger = structlog.get_logger(__name__)
       return _cached_logger
   ```

2. **Schema Lazy Loading**

   ```python
   # Before: All schemas loaded at import
   from agent.core.schema import SkillManifest, ComplexityLevel, ...

   # After: On-demand loading
   def __getattr__(name):
       if name in _loaded_schemas:
           return _loaded_schemas[name]
       mod = _schema_registry.get(name)
       if mod:
           schema_module = import_module(mod, package=__name__)
           obj = getattr(schema_module, name)
           _loaded_schemas[name] = obj
           return obj
   ```

3. **RepomixCache Lazy Creation**

   ```python
   # Before: Created immediately
   context_cache = RepomixCache(target_path=skill_path)

   # After: Created only when accessed
   @property
   def context_cache(self):
       if self._context_cache is None and self._context_path is not None:
           self._context_cache = RepomixCache(target_path=self._context_path)
       return self._context_cache
   ```

### Phase 31: Pre-compiled Regex

Location: `mcp_core/execution/security.py`

**Before:** Regex patterns compiled on every call

```python
for pattern in DANGEROUS_PATTERNS:
    if re.search(pattern, full_cmd, re.IGNORECASE):  # O(n) compile
```

**After:** Patterns pre-compiled at module load

```python
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]
```

**Result:** 70% faster (0.137s → 0.040s for 20,000 calls)

### Hot Path vs Setup Path

Per ODEP 80/20 matrix:

| Path       | Focus                                         | Optimization               |
| ---------- | --------------------------------------------- | -------------------------- |
| Hot Path   | `get_setting()`, `check_dangerous_patterns()` | Pre-compile, O(1) lookups  |
| Setup Path | Module imports                                | Fast single-source imports |

## Version History

| Version | Date       | Changes                                      |
| ------- | ---------- | -------------------------------------------- |
| 2.3.0   | 2026-01-07 | Phase 32: Path utilities (SKILLS_DIR)        |
| 2.2.0   | 2026-01-07 | Phase 32: Import optimizations (117x faster) |
| 2.1.0   | 2026-01-07 | Phase 31: Performance optimizations          |
| 2.0.0   | 2026-01-07 | Phase 30: Fully modular architecture         |
| 1.0.0   | Earlier    | Monolithic single-file modules               |

## Testing

```bash
# All tests
just test-mcp

# Stress tests
uv run pytest packages/python/agent/src/agent/tests/stress_tests/

# Performance benchmarks
uv run pytest packages/python/agent/src/agent/tests/stress_tests/test_performance_omni.py -v
```

## Backward Compatibility

All exports maintained through `mcp_core/__init__.py`:

```python
from mcp_core import (
    # From protocols
    ISafeExecutor, IInferenceClient,
    # From execution
    SafeExecutor, check_dangerous_patterns,
    # From settings (via common.settings)
    Settings, get_setting,
    # ... and more
)
```
