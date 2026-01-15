# Omni-DevEnv Testing System - Developer Guide

> Test system architecture, patterns, and maintenance guidelines.
> Last Updated: 2026-01-15 (Phase 67+)

---

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Rust Tests](#rust-tests)
- [Python Tests](#python-tests)
- [Utilities](#utilities)
- [Fixtures Reference](#fixtures-reference)
- [Testing Patterns](#testing-patterns)
- [Performance Tests](#performance-tests)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Test System Architecture

```
packages/python/agent/src/agent/tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── test_*.py                # Main test suite
├── stress_tests/            # Performance and stress tests
│   ├── test_kernel_stress.py
│   └── test_system_stress.py
├── fakes/                   # Fake implementations for testing
│   ├── fake_vectorstore.py
│   ├── fake_mcp_server.py
│   └── fake_inference.py
└── utils/                   # Testing utilities and fixtures
    ├── __init__.py
    ├── fixtures.py
    ├── assertions.py
    └── async_helpers.py
```

### Test Performance

| Suite        | Execution Time | Parallel |
| ------------ | -------------- | -------- |
| Main Tests   | ~25s           | `-n 3`   |
| Stress Tests | ~15s           | -        |

---

## Test Structure

### File Naming Conventions

| Pattern         | Purpose                           |
| --------------- | --------------------------------- |
| `test_*.py`     | Main test files                   |
| `stress_tests/` | Performance and stress tests      |
| `fakes/`        | Mock implementations              |
| `tests/utils/`  | Shared utilities and test helpers |

### Test Categories

| Type        | Class Prefix  | Purpose                   |
| ----------- | ------------- | ------------------------- |
| Unit        | `Test*`       | Pure logic tests, zero IO |
| Integration | `Test*`       | Module interaction tests  |
| Stress      | `Test*Stress` | Load and stability tests  |

---

## Rust Tests

Located in `packages/rust/crates/omni-*/src/*.rs` with inline `#[cfg(test)]` modules.

### Running Rust Tests

```bash
# Run all tests
cargo test -p omni-vector

# Run specific test
cargo test -p omni-vector test_matches_filter
```

### Test Files

| Crate        | Test Focus                      |
| ------------ | ------------------------------- |
| omni-vector  | Vector store, search, filtering |
| omni-scanner | Script scanning, AST patterns   |
| omni-tags    | Tag extraction, code patterns   |

### Adding Rust Tests

```rust
// packages/rust/crates/omni-vector/src/search.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_feature() {
        // Test implementation
    }
}
```

---

## Python Tests

### Running Tests

```bash
# Run all tests
just test

# Run specific test file
python -m pytest packages/python/agent/src/agent/tests/test_one_tool.py -v

# Run stress tests only
python -m pytest packages/python/agent/src/agent/tests/stress_tests/ -v

# Run with timing
python -m pytest packages/python/agent/src/agent/tests/ -v --durations=10
```

### Performance Test Files

| File                    | Tests                               |
| ----------------------- | ----------------------------------- |
| `test_kernel_stress.py` | Kernel resilience, load latency     |
| `test_system_stress.py` | System-wide stress, RAG performance |

---

## Utilities

### Toxic Skill Templates

Located in `tests/utils/fixtures.py`, using dictionary-based factory pattern:

```python
from agent.tests.utils.fixtures import (
    TOXIC_SKILL_TEMPLATES,
    create_toxic_skill_factory,
)

TOXIC_SKILL_TEMPLATES = {
    "syntax_error": "...",
    "import_error": "...",
    "runtime_error": "...",
}

factory = create_toxic_skill_factory(SKILLS_DIR())
name, module = factory("toxic_skill", "syntax_error")
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
```

### Registry Fixtures

```python
@pytest.fixture
def isolated_registry(registry_fixture):
    """Registry isolated per test (recommended)"""
    registry_fixture.loaded_skills.clear()
    registry_fixture.module_cache.clear()
    return registry_fixture
```

### Vector Store Fixtures

```python
@pytest.fixture
def fake_vector_store():
    """FakeVectorStore instance"""
    from tests.fakes import FakeVectorStore
    return FakeVectorStore()

@pytest.fixture
async def vector_memory():
    """Real VectorMemory instance for integration tests"""
    from agent.core.vector_store import get_vector_memory
    vm = get_vector_memory()
    yield vm
    # Cleanup handled by test teardown
```

### Mock Fixtures

```python
@pytest.fixture
def mock_mcp_server():
    """Mock MCP server"""
    mock = MagicMock()
    mock.list_tools = AsyncMock(return_value=[])
    return mock
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

### Vector Store with Filtering

```python
# Test RAG domain filtering (omni-vector)
@pytest.mark.asyncio
async def test_rag_domain_filtering(vector_memory):
    # Add documents with different domains
    await vector_memory.add(
        documents=["Python code", "Rust code", "Test code"],
        ids=["py_1", "rust_1", "test_1"],
        metadatas=[
            {"domain": "python"},
            {"domain": "rust"},
            {"domain": "testing"}
        ],
    )

    # Filter by domain
    results = await vector_memory.search(
        "code pattern",
        n_results=5,
        where_filter={"domain": "python"}
    )

    assert len(results) > 0
    assert results[0].metadata.get("domain") == "python"
```

---

## Performance Tests

### Benchmarks

| Test               | Threshold | Description              |
| ------------------ | --------- | ------------------------ |
| Cold load latency  | < 200ms   | First skill load         |
| Hot reload latency | < 5ms     | Already loaded skill     |
| Vector search      | < 50ms    | RAG query with filtering |
| Manifest parsing   | < 2.5ms   | YAML Frontmatter parse   |

### Adding Performance Tests

```python
# stress_tests/test_new_feature.py
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
            await do_something()
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print(f"\n[Performance] Feature avg: {avg_latency:.2f}ms")
        assert avg_latency < 100, f"Too slow: {avg_latency:.2f}ms"
```

---

## Best Practices

| Scenario           | Recommended Approach                         |
| ------------------ | -------------------------------------------- |
| Simple skill test  | `def test_git(git): ...`                     |
| Isolated test      | `async def test_git(isolated_registry, ...)` |
| Type safety needed | Use fakes for vector store, MCP server       |
| Error handling     | Use toxic_skill_factory                      |
| Clean state        | Use `reset_singletons` fixture               |

### 1. Use isolated_registry

```python
async def test_git_skill(isolated_registry, mock_mcp_server):
    await isolated_registry.load_skill("git", mock_mcp_server)
```

### 2. Use Fakes Instead of Mocks

```python
async def test_search(fake_vector_store):
    await fake_vector_store.add_documents("col", ["doc"], ["id"])
    results = await fake_vector_store.search("col", "doc")
```

### 3. Don't Modify Production Code

```python
with patch("agent.core.router.semantic_router.get_skill_registry") as mock:
    # Test code
    pass
```

### 4. Clean Test State

```python
@pytest.fixture
def clean_state(reset_singletons):
    yield
    # Automatic cleanup
```

### 5. Avoid if/elif Chains in Tests

```python
# GOOD: Use dictionary-based factory
from tests.utils.fixtures import create_toxic_skill_factory
factory = create_toxic_skill_factory(SKILLS_DIR())
```

---

## Troubleshooting

### Issue: asyncio.run() Error - "Already running asyncio"

**Symptom**: `RuntimeError: asyncio.run() cannot be called from a running event loop`

**Solution**: Use ThreadPoolExecutor for sync-to-async bridging:

```python
import concurrent.futures

def _load():
    return asyncio.run(loader.load_metadata(skill_path))

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    metadata = executor.submit(_load).result()
```

### Issue: Test Isolation Failure

**Symptom**: Test A affects Test B results

**Solution**: Use `isolated_registry` and `reset_singletons`

### Issue: Parallel Test Failure

**Symptom**: Some tests fail under `-n 4` mode

**Solution**:

1. Ensure each test uses `isolated_registry`
2. Avoid `scope="session"` shared state
3. Use `cleanup_threads` fixture

### Issue: Vector Store - Table not found

**Symptom**: `Table not found: collection_name`

**Solution**: Ensure documents are added before searching. The table is created lazily on first add.

### Issue: Vector Store - Arrow error on add

**Symptom**: `all columns in a record batch must have the same length`

**Cause**: `metadatas` parameter passed as dict instead of list

**Solution**:

```python
# WRONG
metadatas={"type": "test"}

# CORRECT
metadatas=[{"type": "test"}]
```

### Issue: Fixture Not Found

**Symptom**: `Fixture 'xxx' not found`

**Solution**: Ensure test file is in `packages/python/agent/src/agent/tests/`

---

## Related Documentation

- [Skills Documentation](../skills.md) - Skills system
- [Justfile](../justfile) - Test commands
- [pyproject.toml](../pyproject.toml) - Pytest configuration
