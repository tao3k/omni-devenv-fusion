# Omni-Dev Fusion Testing System - Developer Guide

> Test system architecture, patterns, and maintenance guidelines.
> Last Updated: 2026-01-08 (Phase 35.1)

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
| Main Tests   | 539   | ~108s          | `-n 4`   |
| Stress Tests | 22+   | ~2s            | -        |

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

**System behavior**: Pytest runs this directly. Our plugin is loaded but doesn't介入.

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

| Test                     | Threshold | Description                  |
| ------------------------ | --------- | ---------------------------- |
| Cold load latency        | < 200ms   | First skill load             |
| Hot reload latency       | < 5ms     | Already loaded skill         |
| Context retrieval        | < 5ms     | Skill context XML generation |
| Manifest parsing         | < 1ms     | YAML Frontmatter parse       |
| Context switching        | < 5ms     | Rapid skill cycling          |
| RAG retrieval (500 docs) | < 150ms   | Vector search under load     |

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

### Issue: asyncio.run() Error

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

## Related Documentation

- [mcp_core Architecture](./mcp-core-architecture.md) - Shared library documentation
- [Trinity Architecture](../explanation/trinity-architecture.md) - Core architecture
- [Skills Documentation](../skills.md) - Skills system
- [Justfile](../justfile) - Test commands
- [pyproject.toml](../pyproject.toml) - Pytest configuration
