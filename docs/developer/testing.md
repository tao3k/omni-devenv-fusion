# Omni-Dev Fusion Testing System - Developer Guide

> Test system architecture, patterns, and maintenance guidelines.
> Last Updated: 2026-01-07

---

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
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
name, module = factory("toxic_syntax", "syntax_error")
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
| Manifest parsing         | < 1ms     | JSON parse + validation      |
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

## Related Documentation

- [Trinity Architecture](../explanation/trinity-architecture.md) - Core architecture
- [Skills Documentation](../skills.md) - Skills system
- [Justfile](../justfile) - Test commands
- [pyproject.toml](../pyproject.toml) - Pytest configuration
