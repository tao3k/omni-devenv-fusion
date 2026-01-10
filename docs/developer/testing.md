# Omni-Dev Fusion Testing System - Developer Guide

> Test system architecture, patterns, and maintenance guidelines.
> Last Updated: 2026-01-09 (Phase 35.2)

---

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Skill Tests (Phase 35.1)](#skill-tests-phase-351)
- [Utilities](#utilities)
- [Fixtures Reference](#fixtures-reference)
- [Fake Implementations](#fake-implementations)
- [Testing Patterns](#testing-patterns)
- [Performance Tests](#performance-tests)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Refactoring History](#refactoring-history)

---

## Overview

### Test System Architecture

```
packages/python/agent/src/agent/tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── test_*.py                # Main test suite (~539 tests)
├── stress_tests/            # Performance and stress tests
│   ├── conftest.py
│   ├── test_kernel_stress.py
│   ├── test_system_stress.py
│   └── test_performance_*.py
├── fakes/                   # Fake implementations for testing
│   ├── fake_vectorstore.py
│   ├── fake_mcp_server.py
│   ├── fake_inference.py
│   └── fake_registry.py
└── utils/                   # Testing utilities and fixtures
    ├── __init__.py
    ├── fixtures.py          # Toxic skill templates, loaders
    ├── assertions.py        # Common assertion helpers
    ├── async_helpers.py     # Async utilities
    └── module_helpers.py    # Module loading utilities
```

### Test Performance

| Suite        | Count | Execution Time | Parallel |
| ------------ | ----- | -------------- | -------- |
| Main Tests   | 610   | ~25s           | `-n 3`   |
| Stress Tests | 22+   | ~2s            | -        |

### Hot Reload Testing (Phase 35.2)

The test system includes comprehensive hot-reload tests for skills:

```python
# packages/python/agent/src/agent/tests/test_one_tool.py

class TestSkillManagerHotReload:
    """Test SkillManager hot reload functionality for tools.py and scripts/*."""

    def test_ensure_fresh_detects_tools_py_changes(self, fresh_manager):
        """_ensure_fresh should detect when tools.py is modified."""
        # Touch tools.py and verify reload is triggered

    def test_ensure_fresh_detects_scripts_changes(self, fresh_manager):
        """_ensure_fresh should detect when scripts/* files are modified."""
        # Touch scripts/status.py and verify reload is triggered

    def test_module_loader_clears_scripts_on_reload(self, fresh_manager):
        """module_loader should clear scripts/* modules when reloading tools."""
        # Verify scripts modules are cleared on hot reload

    def test_hot_reload_preserves_skill_commands(self, fresh_manager):
        """Hot reload should preserve skill commands after reload."""
        # Verify commands still work after reload

    def test_hot_reload_with_both_tools_and_scripts(self, fresh_manager):
        """Hot reload should work when both tools.py and scripts/* are modified."""
        # Verify reload works with multiple changes
```

#### Hot Reload Mechanism

```
User modifies skills/<skill>/tools.py or scripts/*.py
                    ↓
mcp_server.py: omni() calls manager.run()
                    ↓
skill_manager.py: _ensure_fresh() checks mtime
                    ↓
├─ tools.py mtime > skill.mtime → trigger reload
├─ scripts/*.py mtime > skill.mtime → trigger reload
                    ↓
module_loader.py: load_module(reload=True)
                    ↓
├─ Delete sys.modules["agent.skills.<skill>.tools"]
├─ Delete sys.modules["agent.skills.<skill>.scripts.*"]
└─ Re-exec module from file
```

**Key Files**:

- `agent/core/skill_manager.py:488-549` - `_ensure_fresh()` with scripts/\* monitoring
- `agent/core/module_loader.py:167-175` - scripts/\* module cleanup on reload

---

## Testing Layers (Phase 35.2 Atomic Skills)

Omni-DevEnv uses layered testing strategies that perfectly align with the Atomic Skills architecture:

```
assets/skills/git/
├── tools.py              # Interface Layer (testing routing and parameters)
├── scripts/              # Logic Layer (testing business logic)
│   ├── __init__.py
│   ├── status.py
│   └── prepare.py
└── tests/                # Skill Tests
    ├── test_logic.py     # Direct import of scripts/* for testing
    └── test_interface.py # Test interface using git fixture
```

### Layer 1: Logic Tests (`scripts/`)

Purpose: Pure Python unit tests focused on business logic and algorithms

```python
# assets/skills/git/tests/test_logic.py
from ..scripts.rendering import render_commit_message

def test_render_commit_message():
    """Test rendering logic without MCP or Fixture"""
    result = render_commit_message(
        changes=[{"file": "test.py", "type": "M"}],
        conventions={"header_format": "{type}: {scope} - {description}"}
    )
    assert "M test.py" in result
```

**Characteristics**:

- Direct import of script modules
- No Plugin involvement required
- Extremely fast
- Standard Mock/Patch available

### Layer 2: Interface Tests (`tools.py`)

Purpose: Integration tests verifying routing, parameter validation, and system prompts

```python
# assets/skills/git/tests/test_interface.py

def test_git_interface(git):  # 'git' fixture auto-injected
    """Test interface contract"""
    assert hasattr(git, "prepare_commit")
    assert callable(git.prepare_commit)
    assert hasattr(git, "status")
```

**Characteristics**:

- Fixture `git` auto-injected
- Test interface existence
- Verify parameter signatures

**For IDE Autocomplete**: See [IDE Type Hints](#ide-type-hints-no-pyi-generation) section.

### Running Tests

```bash
# Layer 1: Pure logic tests
uv run pytest assets/skills/git/tests/test_logic.py -v

# Layer 2: Interface tests
uv run pytest assets/skills/git/tests/test_interface.py -v

# All skill tests
uv run pytest assets/skills/ -v

# Run via Omni CLI
uv run omni skill test git
```

---

## IDE Type Hints (No .pyi Generation)

Since fixtures are dynamically injected, IDEs cannot automatically infer their types. Here are two Pythonic solutions:

### Option 1: Explicit Type Annotation (Recommended)

Use `TYPE_CHECKING` to import tools modules for static analysis only:

```python
# assets/skills/git/tests/test_git_status.py
import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assets.skills.git import tools as GitTools

@pytest.mark.asyncio
async def test_status_clean(git: "GitTools"):  # String annotation
    # IDE now knows 'git' is GitTools module
    # Type git. and get autocomplete for prepare_commit, status, etc.
    result = await git.status()
    assert result.success
```

**Pros**: Simple, no extra files, works with existing `tools.py` structure.

### Option 2: Unified Skills Context (Implemented) ✅

**Status**: Implemented in `agent/testing/context.py`

Create a centralized type registry for all skills:

```python
# packages/python/agent/src/agent/testing/context.py
from typing import TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from assets.skills.git import tools as git_tools
    from assets.skills.knowledge import tools as knowledge_tools
    from assets.skills.filesystem import tools as filesystem_tools

class SkillsContext:
    """
    Virtual context class for type hints only.

    Runtime behavior:
        - Delegates to pytest fixtures via __getattr__
        - Lazy fixture resolution (only when accessed)

    Type hints:
        - All properties return typed references for IDE autocomplete
        - Actual fixture values returned at runtime
    """
    def __init__(self, request: pytest.FixtureRequest):
        self._request = request
        self._cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._cache:
            return self._cache[name]
        fixture = self._request.getfixturevalue(name)
        self._cache[name] = fixture
        return fixture

    @property
    def git(self) -> "git_tools":
        return self._request.getfixturevalue("git")

    @property
    def knowledge(self) -> "knowledge_tools":
        return self._request.getfixturevalue("knowledge")

    @property
    def filesystem(self) -> "filesystem_tools":
        return self._request.getfixturevalue("filesystem")
```

Registered in `agent/testing/plugin.py`:

```python
@pytest.fixture
def skills_fixture(request: pytest.FixtureRequest) -> "SkillsContext":
    from agent.testing.context import SkillsContext
    return SkillsContext(request)
```

Usage in tests:

```python
# assets/skills/git/tests/test_workflow.py

def test_multi_skill_workflow(skills):  # IDE infers SkillsContext
    # Type skills. → shows .git, .knowledge, .filesystem
    # Type skills.git. → shows prepare_commit, status
    skills.git.init()
    skills.knowledge.get_development_context()
```

### Option 3: Protocol for Contract Testing

Define strict interface contracts:

```python
# agent/testing/protocols.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class GitSkillProtocol(Protocol):
    def prepare_commit(self, message: str) -> dict: ...
    def status(self) -> dict: ...

def test_git_contract(git: GitSkillProtocol):
    # IDE provides hints based on Protocol
    git.prepare_commit("msg")
```

---

## Fixture Collision Prevention

### Reserved Fixture Names

Some skill names would conflict with pytest built-in fixtures. The plugin detects these and warns:

| Reserved      | Reason              |
| ------------- | ------------------- |
| `request`     | Pytest core fixture |
| `cache`       | Pytest caching      |
| `tmpdir`      | Temporary directory |
| `capsys`      | IO capture          |
| `monkeypatch` | Mocking             |
| `mock`        | Mocking             |

**Collision Guard** in `plugin.py`:

```python
RESERVED_FIXTURES = {"request", "config", "cache", "session", "capsys", ...}
PYTEST_BUILTIN_FIXTURES = {...}

def _register_skill_fixture(skill_name: str, skills_root: Path):
    if skill_name in RESERVED_FIXTURES:
        logger.warning(
            f"Skill '{skill_name}' conflicts with pytest fixture. "
            f"Use 'skills.{skill_name}' instead."
        )
```

### Using skills Namespace (Recommended)

If a skill name conflicts, use the `skills` namespace fixture:

```python
def test_conflicting_skill(skills):  # Use skills namespace
    # Instead of request() fixture, use:
    skills.request  # Accesses request fixture via skills

    # For a skill named 'cache':
    skills.cache.init()  # Access skill via namespace
```

---

## Best Practices Summary

| Scenario             | Recommended Approach                            |
| -------------------- | ----------------------------------------------- |
| Simple skill test    | `def test_git(git): ...`                        |
| Multi-skill workflow | `def test_workflow(skills): skills.git.init()`  |
| Type safety needed   | `def test_typed(git: "GitTools"): ...`          |
| Contract testing     | `def test_contract(git: GitSkillProtocol): ...` |
| Conflicting name     | `def test_safe(skills): skills.cache.init()`    |

---

## Test Structure

### File Naming Conventions

| Pattern         | Purpose                                  |
| --------------- | ---------------------------------------- |
| `test_*.py`     | Main test files, executed by `just test` |
| `stress_tests/` | Performance and stress tests             |
| `fakes/`        | Mock implementations (not in test path)  |
| `tests/utils/`  | Shared utilities and test helpers        |

### Test Categories

| Type        | Class Prefix           | Purpose                     |
| ----------- | ---------------------- | --------------------------- |
| Unit        | `Test*`                | Pure logic tests, zero IO   |
| Integration | `Test*`                | Module interaction tests    |
| Performance | `Test*Performance`     | Performance benchmarks      |
| Stress      | `Test*Stress`          | Load and stability tests    |
| Resilience  | `TestKernelResilience` | Error handling and recovery |

---

## Skill Tests (Phase 35.1)

Zero-configuration testing for skill commands with auto-discovered fixtures.

### Directory Structure

```
assets/skills/
├── git/
│   ├── tools.py             # Skill commands with @skill_command decorator
│   └── tests/
│       ├── test_git_commands.py   # Pure pytest, no imports!
│       └── test_git_status.py     # Pure pytest, no imports!
└── knowledge/
    ├── tools.py
    └── tests/
        └── test_knowledge_commands.py  # Pure pytest, no imports!

packages/python/agent/src/agent/testing/
└── plugin.py              # Pytest plugin (auto-loads fixtures)
```

### How It Works

The plugin auto-discovers skills and registers fixtures in `pyproject.toml`:

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "-p agent.testing.plugin --tb=short"
```

This means **no conftest.py, no imports, no configuration** in skill test files.

### Writing Tests (Zero Configuration)

```python
# assets/skills/git/tests/test_git_commands.py

# No imports needed! 'git' fixture is auto-injected.
def test_status_exists(git):
    """Git status command should exist."""
    assert hasattr(git, "status")
    assert callable(git.status)

# Cross-skill tests work too!
def test_integration(git, knowledge):
    assert git.status().success
    assert knowledge.get_development_context().success
```

### Available Fixtures

All skill fixtures are auto-registered:

| Fixture        | Description                      |
| -------------- | -------------------------------- |
| `git`          | Git skill module                 |
| `knowledge`    | Knowledge skill module           |
| `filesystem`   | Filesystem skill module          |
| `<skill_name>` | Any skill in assets/skills/      |
| `skills_root`  | Skills directory (assets/skills) |
| `project_root` | Project root directory           |

### Running Skill Tests

```bash
# Test all skills
uv run omni skill test --all

# Test specific skill
uv run omni skill test git

# Run directly with pytest
uv run pytest assets/skills/ -v
```

---

## Non-Intrusive Design (Framework as Fixture)

The plugin follows the **"Framework as Fixture"** philosophy from Prefect/Django - fixtures are **opt-in**, not forced.

### How It Works

The plugin only injects fixtures when a test explicitly requests them:

```python
# This test uses skill fixtures - plugin provides 'git'
def test_git_status(git):
    assert git.status().success

# This test is completely independent - plugin is transparent!
def test_math_logic():
    assert 1 + 1 == 2
```

### Key Principles

1. **No Interference**: Tests that don't request skill fixtures run normally
2. **Hybrid Support**: Mix skill tests with pure unit tests in the same file
3. **Local Override**: Users can define local fixtures to override plugin ones

### Scenario 1: Pure Unit Tests

```python
# assets/skills/my_tool/tests/test_internal_logic.py
from ..utils import helper_math_function

def test_math_logic():
    """No skill fixtures requested - runs independently."""
    assert helper_math_function(1, 1) == 2
```

**System behavior**: Pytest runs this directly. Our plugin is loaded but doesn't intervene.

### Scenario 2: Mixed Tests

```python
# assets/skills/my_tool/tests/test_mixed.py

def test_pure_logic():
    """No fixture needed."""
    assert calculate() == 42

def test_with_skill(my_tool):
    """Uses skill fixture."""
    assert my_tool.run().success

def test_cross_skill(my_tool, git):
    """Multiple skills in one test."""
    my_tool.sync()
    assert git.status().success
```

### Scenario 3: Local Fixture Override

Users can mock skill fixtures locally:

```python
# assets/skills/git/tests/test_custom.py
import pytest

@pytest.fixture
def git():
    """Local fixture overrides plugin's 'git'."""
    return MockGit()

def test_with_mock(git):
    """Uses local mock, not real skill."""
    assert git.status() == "mocked"
```

**Pytest scope rule**: Local > Plugin, so mocks take precedence.

---

## Test Structure Best Practices

Recommended (not required) directory structure for skills:

```
assets/skills/my_skill/
├── tools.py
└── tests/
    ├── unit/              # Pure logic tests (no skill fixtures)
    │   ├── test_parsers.py
    │   └── test_utils.py
    └── integration/       # Integration tests (use skill fixtures)
        └── test_commands.py
```

This is just a recommendation - you can organize tests any way you prefer.

---

## Utilities

### Toxic Skill Templates

Located in `tests/utils/fixtures.py`, using dictionary-based factory pattern:

```python
from tests.utils.fixtures import (
    TOXIC_SKILL_TEMPLATES,
    create_toxic_skill_factory,
)

# Dictionary-based templates (no if/elif chains)
TOXIC_SKILL_TEMPLATES = {
    "syntax_error": "...",
    "import_error": "...",
    "runtime_error": "...",
    "missing_exposed": "...",
    "circular_import": "...",
    "invalid_exposed_format": "...",
}

# Factory function for creating toxic skills in tests
factory = create_toxic_skill_factory(Path("assets/skills"))
name, module = factory("toxic_skill", "syntax_error")
```

### Skill Loader Utility

```python
from tests.utils.fixtures import load_skill_module_for_test

# Load a skill module directly from file
module = load_skill_module_for_test("git", skills_path)
```

### Assertion Helpers

```python
from tests.utils.fixtures import TestAssertions

# Static assertion methods
TestAssertions.contains("hello world", "hello")
TestAssertions.equal(actual, expected)
TestAssertions.type(obj, str)
TestAssertions.has_attr(obj, "name")
```

---

## Fixtures Reference

All fixtures are defined in `conftest.py`.

### Path Fixtures

```python
@pytest.fixture
def project_root() -> Path:
    """Project root directory"""
    return _PROJECT_ROOT

@pytest.fixture
def skills_path(project_paths) -> Path:
    """Skills directory path"""
    return project_paths["skills"]

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Temporary directory for tests"""
    return tmp_path
```

### Registry Fixtures

```python
@pytest.fixture
def registry_fixture():
    """Clean SkillRegistry instance"""
    import agent.core.registry as sr_module
    sr_module.SkillRegistry._instance = None
    reg = sr_module.get_skill_registry()
    reg.loaded_skills.clear()
    reg.module_cache.clear()
    return reg

@pytest.fixture
def isolated_registry(registry_fixture):
    """Registry isolated per test (recommended)"""
    registry_fixture.loaded_skills.clear()
    registry_fixture.module_cache.clear()
    return registry_fixture
```

### Manager Fixtures

```python
@pytest.fixture
def skill_manager_fixture():
    """SkillManager instance with all skills loaded"""
    import agent.core.skill_manager as sm_module
    sm_module._skill_manager = None
    sm_module._manager = None
    manager = sm_module.get_skill_manager()
    manager.load_all()
    return manager
```

### Toxic Skill Factory Fixture

```python
@pytest.fixture
def toxic_skill_factory(registry):
    """Creates toxic skills for error handling tests"""
    from agent.tests.utils.fixtures import create_toxic_skill_factory
    factory = create_toxic_skill_factory(Path("assets/skills"))
    yield factory
    if hasattr(factory, "cleanup"):
        factory.cleanup()
```

### Cleanup Fixtures

```python
@pytest.fixture
def reset_singletons():
    """Reset all singletons (before and after)"""
    import agent.core.registry as reg_module
    import agent.core.skill_manager as sm_module
    reg_module.SkillRegistry._instance = None
    sm_module._skill_manager = None
    sm_module._manager = None
    yield
    # Automatic reset after

@pytest.fixture
def cleanup_threads():
    """Clean up background threads (use only when needed)"""
    yield
    try:
        from agent.core.bootstrap import shutdown_background_tasks
        shutdown_background_tasks(timeout=2.0)
    except ImportError:
        pass
```

### Mock Fixtures

```python
@pytest.fixture
def mock_mcp_server():
    """Mock MCP server"""
    mock = MagicMock()
    mock.list_tools = AsyncMock(return_value=[])
    mock.list_prompts = AsyncMock(return_value=[])
    mock.list_resources = AsyncMock(return_value=[])
    return mock

@pytest.fixture
def mock_inference():
    """Mock inference client"""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Mocked inference response")
    return mock
```

### Fake Fixtures

```python
@pytest.fixture
def fake_vector_store():
    """FakeVectorStore instance"""
    from tests.fakes import FakeVectorStore
    return FakeVectorStore()

@pytest.fixture
def fake_mcp_server():
    """FakeMCPServer instance"""
    from tests.fakes import FakeMCPServer
    server = FakeMCPServer()
    yield server
    server.clear()

@pytest.fixture
def fake_inference():
    """FakeInference instance"""
    from tests.fakes import FakeInference
    inference = FakeInference()
    yield inference
    inference.clear_responses()
    inference.reset()

@pytest.fixture
def fake_registry():
    """FakeSkillRegistry instance"""
    from tests.fakes import FakeSkillRegistry
    registry = FakeSkillRegistry()
    yield registry
    registry.clear()
```

---

## Fake Implementations

### FakeVectorStore

```python
from tests.fakes import FakeVectorStore

async def test_vector_search(fake_vector_store):
    # Add documents
    await fake_vector_store.add_documents(
        collection="test",
        documents=["doc1", "doc2"],
        ids=["id1", "id2"],
    )

    # Search
    results = await fake_vector_store.search("test", "doc1")

    assert len(results) == 1
    assert results[0]["id"] == "id1"
```

### FakeMCPServer

```python
from tests.fakes import FakeMCPServer

async def test_mcp_tool(fake_mcp_server):
    def git_status():
        return "main"

    fake_mcp_server.add_tool("git.status", git_status, "Get git status")

    result = await fake_mcp_server.call_tool("git.status")
    assert result == "main"
```

### FakeInference

```python
from tests.fakes import FakeInference

async def test_inference(fake_inference):
    fake_inference.set_response("git", {"success": True, "skills": ["git"]})

    result = await fake_inference.complete("git status")
    assert result["success"] is True
```

### FakeSkillRegistry

```python
from tests.fakes import FakeSkillRegistry

async def test_registry(fake_registry):
    fake_registry.add_skill("git", {"name": "git", "version": "1.0.0"})

    skills = fake_registry.list_available_skills()
    assert "git" in skills
```

---

## Testing Patterns

### Correct Async Test

```python
# GOOD: Use @pytest.mark.asyncio
@pytest.mark.asyncio
async def test_feature(isolated_registry, mock_mcp_server):
    success, _ = await isolated_registry.load_skill("git", mock_mcp_server)
    assert success is True
```

### Parametrized Tests

```python
# GOOD: Use @pytest.mark.parametrize
@pytest.mark.parametrize("skill_name", ["git", "filesystem", "knowledge"])
async def test_load_skill(isolated_registry, mock_mcp_server, skill_name):
    success, _ = await isolated_registry.load_skill(skill_name, mock_mcp_server)
    assert success is True
```

### Toxic Skill Testing

```python
# Test error handling with toxic skills
def test_syntax_error_skill(registry, mock_mcp, toxic_skill_factory):
    skill_name, module_name = toxic_skill_factory("toxic_syntax", "syntax_error")

    success, message = registry.load_skill(skill_name, mock_mcp)

    assert success is False
    assert "SyntaxError" in message or "syntax" in message.lower()
```

---

## Performance Tests

### Running Performance Tests

```bash
# Run stress tests only
uv run pytest packages/python/agent/src/agent/tests/stress_tests/ -v

# Run specific test file
uv run pytest packages/python/agent/src/agent/tests/stress_tests/test_kernel_stress.py -v

# With timing output
uv run pytest packages/python/agent/src/agent/tests/ -v --durations=10
```

### Performance Test Files

| File                         | Tests                               |
| ---------------------------- | ----------------------------------- |
| `test_kernel_stress.py`      | Kernel resilience, load latency     |
| `test_system_stress.py`      | System-wide stress, RAG performance |
| `test_performance_skills.py` | Skills loading and execution        |
| `test_performance_omni.py`   | Omni tool dispatch latency          |
| `test_performance_cortex.py` | Semantic Cortex performance         |

### Standalone Benchmark Scripts

```bash
# Full module import benchmark
python scripts/benchmark_full.py

# @omni command invocation benchmark
python scripts/benchmark_omni.py

# Reports saved to .data/ directory
cat .data/benchmark_full_report.txt
cat .data/benchmark_omni_report.txt
```

### @omni Performance Metrics (Phase 32)

| Scenario                      | Time   | Notes                      |
| ----------------------------- | ------ | -------------------------- |
| Cold start (first invocation) | ~65ms  | Includes skill loading     |
| Warm calls (cached skill)     | ~15ms  | Command lookup + execution |
| Command lookup (O(1) cache)   | ~1ms   | Via `_command_cache`       |
| Help commands                 | ~0.2ms | Listing operations         |
| Cross-skill invocation        | ~1.5ms | Different skill            |

**Benchmark Output Example:**

```
=== @omni Performance Benchmark ===

  git.status (cold):     64.4ms
  git.status (warm#1):   15.2ms
  git.status (warm#2):   15.1ms
  git.log:               0.2ms
  git.diff:              10.5ms

  --- Help Commands ---
  omni help:             0.3ms
  omni git:              0.1ms

  --- Cross-Skill ---
  terminal.run:          1.5ms

==================================================
SUMMARY
==================================================
Cold start:  avg=64.4ms
Warm calls:  avg=13.5ms, min=0.2ms, max=18.8ms
Help calls:  avg=0.2ms
Cross-skill: 1.5ms
```

### Import Performance Metrics (Phase 32)

| Module                     | Before | After | Speedup  |
| -------------------------- | ------ | ----- | -------- |
| `agent.core.schema`        | 421ms  | 3.6ms | **117x** |
| `agent.core.skill_manager` | 200ms  | 3.5ms | **57x**  |
| `agent.core.bootstrap`     | 169ms  | 0.8ms | **211x** |
| `agent.mcp_server`         | 156ms  | 0.8ms | **195x** |
| `agent.core.registry`      | 51ms   | 40ms  | 1.3x     |

**Key Optimizations:**

- Lazy structlog initialization (`_get_logger()` pattern)
- Schema `__getattr__` lazy loading
- RepomixCache on-demand creation
- ModuleLoader cached initialization

### Adding New Performance Tests

```python
# stress_tests/test_performance_new.py
import pytest
import time

class TestNewFeaturePerformance:
    @pytest.mark.asyncio
    async def test_feature_latency(self):
        """Test feature latency"""
        iterations = 10
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            # Test code
            await do_something()
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print(f"\n[Performance] Feature avg: {avg_latency:.2f}ms")

        # Set reasonable threshold
        assert avg_latency < 100, f"Too slow: {avg_latency:.2f}ms"
```

### Performance Benchmarks

| Test                  | Threshold | Description                  |
| --------------------- | --------- | ---------------------------- |
| Cold load latency     | < 200ms   | First skill load             |
| Hot reload latency    | < 5ms     | Already loaded skill         |
| Context retrieval     | < 5ms     | Skill context XML generation |
| Manifest parsing      | < 2.5ms   | YAML Frontmatter parse       |
| Manifest cache access | < 1.2ms   | Cached manifest access       |
| Context switching     | < 5ms     | Rapid skill cycling          |

---

## Best Practices

### 1. Use isolated_registry

```python
# GOOD: Each test uses independent registry
async def test_git_skill(isolated_registry, mock_mcp_server):
    await isolated_registry.load_skill("git", mock_mcp_server)
    # ...
```

### 2. Use Fakes Instead of Mocks

```python
# GOOD: Use FakeVectorStore
async def test_search(fake_vector_store):
    await fake_vector_store.add_documents("col", ["doc"], ["id"])
    results = await fake_vector_store.search("col", "doc")
```

### 3. Don't Modify Production Code

```python
# GOOD: Use patches or fakes
with patch("agent.core.router.semantic_router.get_skill_registry") as mock:
    # Test code
    pass
```

### 4. Clean Test State

```python
# GOOD: Use cleanup fixtures
@pytest.fixture
def clean_state(reset_singletons):
    yield
    # Automatic cleanup
```

### 5. Avoid Slow Tests

```python
# If test requires API key, mark as slow
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY"
)
async def test_real_api():
    # ...
```

### 6. Avoid if/elif Chains in Tests

```python
# GOOD: Use dictionary-based factory
from tests.utils.fixtures import create_toxic_skill_factory

factory = create_toxic_skill_factory(Path("assets/skills"))
name, module = factory("toxic_syntax", "syntax_error")

# BAD: if/elif chain
if toxic_type == "syntax_error":
    ...
elif toxic_type == "import_error":
    ...
```

---

## Troubleshooting

### Issue: asyncio.run() Error - "Already running asyncio"

**Symptom**: `RuntimeError: asyncio.run() cannot be called from a running event loop`

**Cause**: Using `FastMCP.run()` which internally calls `anyio.run()` while an event loop already exists

**Solution**: Use async methods directly:

```python
# BAD - FastMCP.run() is synchronous, uses anyio.run() internally
await mcp.run()  # This will fail if called from an async context

# GOOD - Use async methods directly
await mcp.run_stdio_async()  # For stdio transport
await mcp.run_sse_async(mount_path)  # For SSE transport
```

**Files Modified**:

- `packages/python/agent/src/agent/mcp_server.py` - Changed `await mcp.run()` to `await mcp.run_stdio_async()`

### Issue: asyncio.run() Error - "a coroutine was expected"

**Symptom**: `ValueError: a coroutine was expected`

**Cause**: Using sync function call for async function

**Solution**:

```python
# BAD
result = asyncio.run(module.async_function())

# GOOD
result = await module.async_function()
```

### Issue: Test Isolation Failure

**Symptom**: Test A affects Test B results

**Solution**: Use `isolated_registry` and `reset_singletons`

### Issue: Parallel Test Failure

**Symptom**: Some tests fail under `-n 4` mode

**Cause**: Test uses shared state

**Solution**:

1. Ensure each test uses `isolated_registry`
2. Avoid `scope="session"` shared state
3. Use `cleanup_threads` fixture

### Issue: Fixture Not Found

**Symptom**: `Fixture 'xxx' not found`

**Cause**: Fixtures defined in `conftest.py`, wrong import path

**Solution**: Ensure test file is in `packages/python/agent/src/agent/tests/`

### Issue: Unknown toxic_type

**Symptom**: `ValueError: Unknown toxic_type: 'xxx'`

**Solution**: Use valid toxic type from `TOXIC_SKILL_TEMPLATES`:

```python
# Valid types:
# - syntax_error
# - import_error
# - runtime_error
# - missing_exposed
# - circular_import
# - invalid_exposed_format
```

---

## Refactoring History

### 2026-01-09 (Phase 35.2 - Hot Reload & pytest-xdist Fixes)

| Change                | Description                                                       |
| --------------------- | ----------------------------------------------------------------- |
| Hot Reload scripts/\* | `_ensure_fresh()` now monitors both `tools.py` and `scripts/*`    |
| Module Cleanup        | `load_module()` clears `scripts/*` modules on hot reload          |
| Naming Convention     | Unified `skill.command` format (e.g., `git.status`, `git.commit`) |
| pytest-xdist Fix      | `module_loader.py` appends paths instead of overwriting           |
| Test Count            | 610 tests                                                         |

#### pytest-xdist Module Loading Issue

**Problem**: Parallel tests with `-n 4` failed with `ModuleNotFoundError: No module named 'agent.skills.core'`

**Root Cause**: Namespace Package vs. Dynamic Loading conflict. When `conftest.py` pre-creates `agent.skills` with `agent_skills_src` path, then `ModuleLoader._ensure_parent_packages()` sees it already exists and skips updating, causing `agent.skills.core` import to fail.

**Solution - Fix `module_loader.py`**:

```python
def _ensure_parent_packages(self) -> None:
    """Create parent packages for skill modules."""
    # ... agent package setup ...

    skills_dir = str(self.skills_dir)
    if "agent.skills" not in sys.modules:
        # First time: create with assets/skills path
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [skills_dir]
        # ...
    else:
        # Already exists (e.g., pre-loaded by conftest.py for pytest-xdist)
        # FIX: Don't overwrite - append assets/skills to __path__ instead!
        skills_pkg = sys.modules["agent.skills"]
        if hasattr(skills_pkg, "__path__") and skills_dir not in skills_pkg.__path__:
            skills_pkg.__path__.append(skills_dir)
```

**Additional Fixes**:

1. **Added `agent/skills/__init__.py`**:

```python
# packages/python/agent/src/agent/skills/__init__.py
"""agent.skills - Skill modules package"""
from .decorators import skill_command, CommandResult
```

2. **Pre-load in `registry/core.py`**:

```python
# Top of file - pre-load for pytest-xdist
import agent.skills.core  # noqa: F401
```

3. **Session fixture in `conftest.py`**:

```python
@pytest.fixture(scope="session", autouse=True)
def _ensure_agent_skills_loaded():
    """Ensure agent.skills package is loaded for all tests."""
    import agent.skills
    import agent.skills.core
    assert "agent.skills" in sys.modules
    assert "agent.skills.core" in sys.modules
    yield
```

4. **Robust import in `get_skill_manifest()`**:

```python
try:
    from agent.skills.core.skill_manifest_loader import get_manifest_loader
except ModuleNotFoundError:
    import importlib
    import sys
    if "agent.skills" not in sys.modules:
        import agent.skills
    if "agent.skills.core" not in sys.modules:
        import agent.skills.core
    skill_manifest_loader = importlib.import_module("agent.skills.core.skill_manifest_loader")
    get_manifest_loader = skill_manifest_loader.get_manifest_loader
```

5. **Updated `justfile`**:

```bash
# Use 3 workers instead of 4 for stability
uv run pytest packages/python/agent/src/agent/tests/ -n 3 --ignore=... -v
```

**Key Files**:

- `agent/core/module_loader.py` - **FIX**: Append paths instead of overwriting
- `agent/skills/__init__.py` - Package init file
- `agent/core/registry/core.py` - Pre-load and robust import
- `agent/tests/conftest.py` - Session-scoped autouse fixture

**Test Results**:

```
✅ 610 passed, 2 skipped (pytest-xdist stable with 3 workers)
```

| Change                   | Description                                                      |
| ------------------------ | ---------------------------------------------------------------- |
| prepare_commit Migration | Complete `prepare_commit` implementation in `scripts/prepare.py` |
| Cascading Templates      | Created `prepare_result.j2` for structured output                |
| Module Loader Fix        | Added `_ensure_skill_package()` for subpackage imports           |
| Test Framework Fix       | Updated `load_skill_module` with proper package context setup    |
| Test Count               | 539 → 604 tests                                                  |

**Key Files**:

- `assets/skills/git/scripts/prepare.py` - Complete prepare_commit workflow
- `assets/skills/git/templates/prepare_result.j2` - Cascading template
- `packages/python/agent/src/agent/core/module_loader.py` - Module loading fixes
- `packages/python/agent/src/agent/tests/test_decorators.py` - Package context setup

### 2026-01-08 (Phase 35.1 - Zero-Configuration Test Framework)

| Change         | Description                                                     |
| -------------- | --------------------------------------------------------------- |
| Pytest Plugin  | Created `agent/testing/plugin.py` for auto-fixture registration |
| No conftest.py | Completely eliminated `assets/skills/conftest.py`               |
| Auto-load      | Plugin auto-loaded via `pyproject.toml` `addopts`               |
| Non-intrusive  | Fixtures are opt-in, not forced                                 |

**Key Files:**

- `packages/python/agent/src/agent/testing/plugin.py` - Pytest plugin (auto-discovers skills, registers fixtures)
- `pyproject.toml` - Auto-loads plugin via `addopts = "-p agent.testing.plugin"`
- `assets/skills/git/tests/test_git_commands.py` - Pure pytest, no imports
- `assets/skills/knowledge/tests/test_knowledge_commands.py` - Pure pytest, no imports

**Test Results:**

```
23 tests passed (git: 13, knowledge: 10)
uv run pytest assets/skills/ -v  ✅
uv run omni skill test --all    ✅
```

**Example Test File (Before):**

```python
# Old approach - required imports and conftest.py
from agent.skills.core.test_framework import test
pytest_plugins = ["agent.testing.plugin"]

@test
def test_status_exists(git):
    assert git.status().success
```

**Example Test File (After):**

```python
# New approach - zero configuration!
def test_status_exists(git):  # 'git' fixture auto-injected
    assert git.status().success
```

### 2026-01-08 (Phase 33 - SKILL.md Unified Format)

| Change             | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| SKILL.md Migration | Replaced manifest.json with YAML Frontmatter in SKILL.md          |
| Test Fixtures      | Updated test fixtures to create SKILL.md instead of manifest.json |
| Manifest Cleanup   | Removed dependencies/permissions from SKILL.md frontmatter        |

### 2026-01-07 (Phase 32 - Import & Performance Optimization)

| Change                     | Description                                              |
| -------------------------- | -------------------------------------------------------- |
| Lazy Logger Pattern        | `_get_logger()` avoids import-time structlog overhead    |
| Schema Lazy Loading        | `__getattr__` for on-demand Pydantic model loading       |
| RepomixCache Lazy Creation | `@property` defers cache creation until accessed         |
| ModuleLoader Caching       | `_get_module_loader()` reuses single instance            |
| Benchmark Scripts          | `scripts/benchmark_full.py`, `scripts/benchmark_omni.py` |
| Core Skills Preload        | `boot_core_skills(mcp)` called at MCP startup            |

**Performance Improvements:**

- Schema import: 421ms → 3.6ms (117x)
- SkillManager import: 200ms → 3.5ms (57x)
- Bootstrap import: 169ms → 0.8ms (211x)
- MCP server import: 156ms → 0.8ms (195x)

### 2026-01-07 (Phase 29 - Refactoring)

| Change                          | Description                                                |
| ------------------------------- | ---------------------------------------------------------- |
| Created tests/utils/fixtures.py | Centralized toxic skill templates (dict-based, no if/elif) |
| Created tests/utils/**init**.py | Unified exports for testing utilities                      |
| Refactored test_kernel_stress   | 80-line if/elif chain → 15-line dictionary factory         |
| Test Count Update               | 496 → 539 tests                                            |
| Stress Tests Isolated           | Moved to dedicated `stress_tests/` directory               |

### 2026-01-05 (Phase 1-3)

| Change                  | Description                                                      |
| ----------------------- | ---------------------------------------------------------------- |
| Fixture Consolidation   | All fixtures moved to `conftest.py`                              |
| Removed async_helpers   | Removed deprecated `run_async()`                                 |
| Performance Tests Moved | To `stress_tests/`                                               |
| New fakes/              | FakeVectorStore, FakeMCPServer, FakeInference, FakeSkillRegistry |
| Speed Improvement       | 95s → 9s (parallel)                                              |
| File Renaming           | `test_phase*.py` → `test_*.py`                                   |

---

## Debugging Session Log

### 2026-01-08: Parallel Testing Event Loop Issue

**Problem**: 20 tests failed with `asyncio.run() cannot be called from a running event loop`

**Root Cause**: `get_skill_manifest()` in `agent/core/registry/core.py` used `asyncio.run()` which conflicts with pytest-asyncio's running event loop in parallel tests.

**Failed Tests**:

```
test_delegate_mission.py::TestCoderAgent::test_coder_agent_run_does_not_raise
test_neural_bridge.py::TestActiveRAG::* (9 tests)
test_skills.py::TestFilesystemSkill::* (5 tests)
test_system_stress.py::TestSystemEndurance::* (2 tests)
test_agent_handoff.py::TestCoderAgent/ReviewerAgent (2 tests)
```

**Solution**:

1. Run async code in ThreadPoolExecutor to isolate event loops:

```python
import asyncio
import concurrent.futures

def _load():
    return asyncio.run(loader.load_metadata(skill_path))

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    metadata = executor.submit(_load).result()
```

2. Updated performance thresholds:
   - `test_manifest_cache_stress`: 0.5ms → 0.8ms (ThreadPoolExecutor overhead)

**Files Modified**:

- `packages/python/agent/src/agent/core/registry/core.py` - `get_skill_manifest()`
- `packages/python/agent/src/agent/tests/stress_tests/test_system_stress.py` - Threshold update

### 2026-01-08: toxic_skill_factory Path Issue

**Problem**: `toxic_skill_factory` used `Path("assets/skills")` which doesn't resolve correctly when skills are in a different directory.

**Solution**:

```python
# Before
factory = create_toxic_skill_factory(Path("assets/skills"))

# After
from common.skills_path import SKILLS_DIR
factory = create_toxic_skill_factory(SKILLS_DIR())
```

**Files Modified**:

- `packages/python/agent/src/agent/tests/stress_tests/test_kernel_stress.py`

### 2026-01-08: --cache-clear Ineffectiveness

**Problem**: `--cache-clear` in justfile was believed to fix parallel test issues, but it only clears pytest cache, not Python module cache.

**Solution**: Removed `--cache-clear` from `just test` command.

**Files Modified**:

- `justfile`

### 2026-01-08: Module Clearing in test_one_tool.py

**Problem**: `test_all_skills_load_with_decorators` cleared ALL `agent.skills.*` modules including `agent.skills.core` (the newly created core module).

**Solution**: Added exclusion for `agent.skills.core`:

```python
modules_to_clear = [
    k for k in sys.modules.keys()
    if k.startswith("agent.skills") and k != "agent.skills.core"
]
```

**Files Modified**:

- `packages/python/agent/src/agent/tests/test_one_tool.py`

---

### 2026-01-08: Phase 34 - CommandResult and StateCheckpointer

**Changes**:

1. `@skill_command` decorator now returns `CommandResult` instead of raw data
2. Added `StateCheckpointer` for cross-session state persistence
3. `SkillMetadata` uses `@dataclass(slots=True)` which has no `__dict__`

**Failed Tests**:

```
test_one_tool.py::TestSkillManagerLoading::test_skill_command_decorator_works
test_shim_pattern.py::TestShimPatternManifest::test_default_execution_mode_library
test_telemetry.py::TestOrchestratorSessionIntegration::*
```

**Solutions**:

1. **Use `unwrap_command_result()` helper for tests**:

```python
from agent.skills.decorators import skill_command

@skill_command(name="test", category="test")
def test_func():
    return "result"

# Tests should unwrap the result
result = unwrap_command_result(test_func())
assert result == "result"
```

2. **Use direct field access for `SkillMetadata`** (no `__dict__`):

```python
# Before (fails with slots=True)
new_metadata = SkillMetadata(**metadata.__dict__)

# After (correct)
new_metadata = SkillMetadata(
    name=metadata.name,
    version=metadata.version,
    routing_keywords=new_keywords,
    ...
)
```

3. **Mock `get_checkpointer` in Orchestrator tests**:

```python
with patch("agent.core.orchestrator.SessionManager") as mock_session:
    with patch("agent.core.orchestrator.get_checkpointer") as mock_checkpointer:
        mock_session.return_value = MagicMock()
        mock_checkpointer.return_value = MagicMock()
        orchestrator = Orchestrator()
```

**Files Modified**:

- `packages/python/agent/src/agent/core/registry/adapter.py` - `_inject_omni_defaults()`
- `packages/python/agent/src/agent/core/skill_manager.py` - ThreadPoolExecutor pattern
- `packages/python/agent/src/agent/core/state.py` - New StateCheckpointer
- `packages/python/agent/src/agent/tests/test_skills.py` - `unwrap_command_result()` helper
- `packages/python/agent/src/agent/tests/test_one_tool.py` - Updated tests
- `packages/python/agent/src/agent/tests/test_telemetry.py` - Mock checkpointer

---

## 2026-01-09 Debugging Session Log

### 2026-01-09: ModuleNotFoundError for agent.skills.git During Test Execution

**Problem**: Tests failed with `ModuleNotFoundError: No module named 'agent.skills.git'` when executing commands like `status_report` that import from `agent.skills.git.scripts`.

**Root Cause**: The module loader was deleting parent packages during hot-reload, breaking the import chain for subpackage imports like `from agent.skills.git.scripts import xxx`.

**Failed Tests**:

```
packages/python/agent/src/agent/tests/test_decorators.py::TestSkillDirectCalls::test_git_hotfix_returns_plan
packages/python/agent/src/agent/tests/test_one_tool.py::TestOmniDispatch::test_dispatch_git_status
packages/python/agent/src/agent/tests/test_one_tool.py::TestSkillManagerLoading::test_git_skill_has_prepare_commit_command
packages/python/agent/src/agent/tests/test_one_tool.py::TestSkillManagerLoading::test_git_commands_are_skill_command_decorated
packages/python/agent/src/agent/tests/test_pydantic_schema.py::TestGitSkill::test_git_skill_has_error_class
packages/python/agent/src/agent/tests/test_skills.py::TestSkillManagerOmniCLI::test_skill_manager_fixture_run_command
```

**Solutions**:

1. **Fixed `load_skill_module` in `test_decorators.py`**:

```python
def _setup_skill_package_context(skill_name: str, skills_root: Path):
    """Set up package context for skill module loading."""
    from importlib import util
    from common.gitops import get_project_root

    project_root = get_project_root()

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        agent_pkg.__file__ = str(agent_src / "__init__.py")
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        skills_pkg.__file__ = str(skills_root / "__init__.py")
        sys.modules["agent.skills"] = skills_pkg
        sys.modules["agent"].skills = skills_pkg

    # Pre-load decorators module (required for @skill_command)
    if "agent.skills.decorators" not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = util.spec_from_file_location("agent.skills.decorators", decorators_path)
            if spec and spec.loader:
                module = util.module_from_spec(spec)
                sys.modules["agent.skills.decorators"] = module
                sys.modules["agent.skills"].decorators = module
                spec.loader.exec_module(module)

    # Ensure 'agent.skills.{skill_name}' package exists
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name not in sys.modules:
        skill_pkg = types.ModuleType(skill_pkg_name)
        skill_pkg.__path__ = [str(skills_root / skill_name)]
        skill_pkg.__file__ = str(skills_root / skill_name / "__init__.py")
        sys.modules[skill_pkg_name] = skill_pkg
```

2. **Fixed module loader in `core/module_loader.py`**:

```python
def _ensure_skill_package(self, skill_name: str) -> None:
    """Ensure skill-specific package exists (needed for subpackage imports)."""
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name in sys.modules:
        return

    skill_pkg_path = self.skills_dir / skill_name
    if not skill_pkg_path.exists():
        return

    skill_pkg = types.ModuleType(skill_pkg_name)
    skill_pkg.__path__ = [str(skill_pkg_path)]
    skill_pkg.__file__ = str(skill_pkg_path / "__init__.py")
    sys.modules[skill_pkg_name] = skill_pkg

    # Also set as attribute on parent
    parent_pkg = sys.modules.get("agent.skills")
    if parent_pkg:
        setattr(parent_pkg, skill_name, skill_pkg)
```

3. **Removed parent package deletion in `load_module()`**:

```python
# Before (problematic)
if parent_name and parent_name in sys.modules:
    del sys.modules[parent_name]

# After (fixed - keep parent package for subpackage imports)
# NOTE: Do NOT clear parent package - it's needed for subpackage imports
# The parent package (e.g., '') must exist for
# imports like 'from agent.skagent.skills.gitills.git.scripts import xxx' to work
```

4. **Updated test expectations**:
   - `test_one_tool.py`: Changed assertion from `execute_commit` to `commit`
   - `test_pydantic_schema.py`: Updated error class test to check scripts/ directory for result dict pattern

5. **Added missing `current_branch` function** in `scripts/status.py`:

```python
def current_branch(project_root: Path = None) -> str:
    """Get current branch name."""
    branch, rc = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    return branch if rc == 0 else ""
```

**Files Modified**:

- `packages/python/agent/src/agent/tests/test_decorators.py` - Fixed `load_skill_module` and added `_setup_skill_package_context`
- `packages/python/agent/src/agent/tests/test_one_tool.py` - Updated test assertions
- `packages/python/agent/src/agent/tests/test_pydantic_schema.py` - Updated error class test
- `packages/python/agent/src/agent/core/module_loader.py` - Added `_ensure_skill_package`, fixed parent package handling
- `assets/skills/git/scripts/status.py` - Added `current_branch` function
- `assets/skills/git/scripts/prepare.py` - Complete `prepare_commit` implementation with cascading templates

**Test Results**:

```
605 passed, 2 skipped (RAG tests require persistent ChromaDB)
```

### 2026-01-09: prepare_commit Migration to Phase 35.2 Architecture

**Changes**:

1. **Migrated `prepare_commit` from `tools.py` to `scripts/prepare.py`**:
   - Added `inject_root=True` decorator parameter
   - Implemented complete workflow: stage → lefthook → re-stage → diff
   - Added scope validation against `cog.toml` with auto-fix
   - Added security scan for sensitive files
   - Created cascading template output via `render_workflow_result`

2. **Created `templates/prepare_result.j2`**:
   - Structured XML output for LLM parsing
   - Supports user overrides in `assets/templates/git/`

3. **Updated `tools.py` router**:

```python
@skill_command(
    name="prepare_commit",
    category="workflow",
    description="Prepare commit: stage all, run checks, return staged diff.",
    inject_root=True,
)
def prepare_commit(project_root: Path = None, message: str = None) -> str:
    from agent.skills.git.scripts import prepare as prepare_mod
    result = prepare_mod.prepare_commit(project_root=project_root, message=message)
    return prepare_mod.format_prepare_result(result)
```

**Files Modified**:

- `assets/skills/git/tools.py` - Updated `prepare_commit` with `inject_root=True`
- `assets/skills/git/scripts/prepare.py` - Complete implementation
- `assets/skills/git/templates/prepare_result.j2` - New template

---

## Related Documentation

- [mcp_core Architecture](./mcp-core-architecture.md) - Shared library documentation
- [Trinity Architecture](../explanation/trinity-architecture.md) - Core architecture
- [Skills Documentation](../skills.md) - Skills system
- [Justfile](../justfile) - Test commands
- [pyproject.toml](../pyproject.toml) - Pytest configuration
