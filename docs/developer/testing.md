# Omni-DevEnv Testing System - Developer Guide

> Test system architecture, patterns, and maintenance guidelines.
> Last Updated: 2026-01-15 (Phase 67+)

---

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Rust Tests](#rust-tests)
- [Python Tests](#python-tests)
- [Pytest Plugin for Skill Tests](#pytest-plugin-for-skill-tests)
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

### Sync Tests (Phase 68+)

| File                        | Tests                                        |
| --------------------------- | -------------------------------------------- |
| `test_vector_store_sync.py` | Path normalization, idempotency, consistency |

#### Key Sync Test Classes

| Class                     | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `TestSyncDiffAlgorithm`   | Pure function tests for diff logic       |
| `TestPathNormalization`   | Path format handling (absolute/relative) |
| `TestSyncIdempotency`     | Running sync twice should be stable      |
| `TestSyncPathConsistency` | DB paths match filesystem paths          |
| `TestSyncEdgeCases`       | Empty DB/filesystem, special chars       |

#### Running Sync Tests

```bash
# Run all sync tests
python -m pytest packages/python/agent/src/agent/tests/unit/test_vector_store_sync.py -v

# Run only path normalization tests
python -m pytest packages/python/agent/src/agent/tests/unit/test_vector_store_sync.py::TestPathNormalization -v

# Run idempotency tests (integration)
python -m pytest packages/python/agent/src/agent/tests/unit/test_vector_store_sync.py::TestSyncIdempotency -v
```

---

## Pytest Plugin for Skill Tests

> Phase 63+: First-class pytest plugin that automatically discovers and registers skill fixtures.
> Inspired by Prefect's test harness pattern - no conftest.py needed!

### Quick Start

Add the plugin to your `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pytest_plugins = ["agent.testing.plugin"]
```

### Automatic Skill Fixtures

The plugin automatically scans `assets/skills/` and creates fixtures for each skill:

```python
# Test file: assets/skills/git/tests/test_git.py

def test_git_status(git):
    """Directly use 'git' fixture - loaded automatically!"""
    result = git.status()
    assert result.success

def test_git_init(git):
    """Another skill fixture - works the same way"""
    result = git.init()
    assert result.success
```

### Fixture Names

| Fixture Name         | Skill Module                      | Description           |
| -------------------- | --------------------------------- | --------------------- |
| `git`                | `agent.skills.git`                | Git operations skill  |
| `filesystem`         | `agent.skills.filesystem`         | File I/O skill        |
| `knowledge`          | `agent.skills.knowledge`          | RAG knowledge skill   |
| `structural_editing` | `agent.skills.structural_editing` | AST refactoring skill |

### Reserved Fixture Names

Some names conflict with pytest built-ins. Use `skills.git` instead:

```python
# WRONG - conflicts with pytest fixture
def test_git_status(git):
    pass

# CORRECT - use skills prefix
def test_git_status(skills):
    skills.git.status()
```

---

### SkillsContext - Unified Access

Access all skills via the `skills` fixture with IDE type hints:

```python
def test_multiple_skills(skills):
    """Access all skills through unified context"""
    # Git operations
    git_status = skills.git.status()

    # File operations
    skills.filesystem.read_file("path/to/file")

    # Knowledge search
    results = skills.knowledge.search("query")
```

---

### Skill Test Patterns

#### Pattern 1: Direct Skill Fixture

```python
# assets/skills/git/tests/test_git.py

def test_status_returns_info(git):
    """Simple test using git fixture directly"""
    result = git.status()
    assert result.success is True
    assert isinstance(result.data, dict)
```

#### Pattern 2: Multiple Skills

```python
def test_file_and_git_workflow(filesystem, git):
    """Test workflow spanning multiple skills"""
    # Read file content
    content = filesystem.read_file("README.md")

    # Git operations
    git.init()
    git.add("README.md")
```

#### Pattern 3: SkillsContext (recommended for type hints)

```python
def test_complex_workflow(skills):
    """Use SkillsContext for better IDE support"""
    # All skills available with autocomplete
    status = skills.git.status()
    files = skills.filesystem.list_directory(".")

    # Chain operations
    if status.data.get("clean"):
        skills.git.commit("Auto-save")
```

---

### Skill Fixture API

Each skill fixture provides:

| Property         | Type               | Description              |
| ---------------- | ------------------ | ------------------------ |
| `skill.name`     | str                | Skill name (e.g., "git") |
| `skill.commands` | dict[str, Command] | Available commands       |
| `skill.metadata` | SkillMetadata      | Skill metadata           |

#### Command Object

```python
# Access skill commands
git = git_fixture  # or skills.git

# List available commands
for name, cmd in git.commands.items():
    print(f"  {name}: {cmd.description}")

# Call command directly
result = git.commands["status"].func()
```

---

### Base Fixtures

The plugin provides these base fixtures automatically:

| Fixture        | Type          | Description                  |
| -------------- | ------------- | ---------------------------- |
| `skills_root`  | Path          | `assets/skills/` directory   |
| `project_root` | Path          | Project root directory       |
| `skills`       | SkillsContext | Unified access to all skills |
| `skills_dir`   | Path          | Alias for `skills_root`      |

```python
def test_paths(skills_root, project_root):
    """Base fixtures for path operations"""
    assert skills_root.name == "skills"
    assert (project_root / "assets/skills").exists()
```

---

### Writing Skill Integration Tests

Place skill tests in the skill's `tests/` directory:

```
assets/skills/
├── git/
│   ├── scripts/
│   │   └── status.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_git.py        # Skill-specific tests
│   └── SKILL.md
```

#### Example: Complete Skill Test File

```python
"""Tests for git skill."""

import pytest


def _get_git_skill():
    """Helper to get git skill (alternative to fixture)."""
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    if not manager._loaded:
        manager.load_all()
    return manager.skills.get("git")


class TestGitStatus:
    """Tests for git status command."""

    def test_status_returns_result(self, git):
        """Test that status command returns expected structure."""
        result = git.status()

        assert result.success
        assert hasattr(result, 'data')

    def test_status_contains_branch(self, git):
        """Test that status includes branch info."""
        result = git.status()

        if result.success:
            assert "branch" in result.data or "current_branch" in result.data


class TestGitSkillRegistration:
    """Tests for skill loading and registration."""

    def test_git_skill_loaded(self, git):
        """Verify git skill is properly loaded."""
        assert git is not None
        assert git.name == "git"

    def test_git_has_expected_commands(self, git):
        """Verify git has expected commands registered."""
        command_names = list(git.commands.keys())

        assert len(command_names) >= 3
        assert "status" in command_names
        assert "init" in command_names

    def test_commands_have_valid_schemas(self, git):
        """Verify all commands have valid input schemas."""
        for cmd_name, cmd in git.commands.items():
            assert isinstance(cmd.input_schema, dict)
            assert "properties" in cmd.input_schema
```

---

### Running Skill Tests

```bash
# Run all skill tests
uv run pytest assets/skills/*/tests/ -v

# Run specific skill tests
uv run pytest assets/skills/git/tests/ -v

# Run single test file
uv run pytest assets/skills/git/tests/test_git.py::TestGitStatus::test_status_returns_result -v

# Run with coverage
uv run pytest assets/skills/*/tests/ --cov=agent.skills
```

---

### Test Data

Place test data in the skill's `tests/test_data/` directory:

```
assets/skills/structural_editing/
├── scripts/
├── tests/
│   ├── test_structural_editing.py
│   ├── test_data/
│   │   ├── sample.py
│   │   ├── sample.rs
│   │   └── sample.js
```

```python
from pathlib import Path

def _get_test_file(name):
    """Get path to test file in test_data directory."""
    return Path(__file__).parent / "test_data" / name


def test_with_sample_file(git):
    """Test using sample file from test_data."""
    sample_file = _get_test_file("sample.py")
    content = sample_file.read_text()

    # Use content in test
    assert "def" in content
```

---

### Troubleshooting

#### Issue: Fixture Not Found

**Symptom**: `Fixture 'xxx' not found`

**Solution**: Ensure the skill exists in `assets/skills/`:

```bash
ls assets/skills/  # Check skill directories
```

#### Issue: Import Error for agent.skills

**Symptom**: `ImportError: attempted relative import with no known parent package`

**Cause**: The plugin handles this automatically, but tests outside the pytest plugin context may fail.

**Solution**: Use SkillManager directly:

```python
from agent.core.skill_manager import get_skill_manager

def test_skill():
    manager = get_skill_manager()
    skill = manager.skills.get("git")
```

#### Issue: Skill Has No Scripts

**Symptom**: `Skill 'xxx' has no scripts/*.py (tools.py pattern removed)`

**Cause**: Skill doesn't have `scripts/*.py` files with `@skill_script` decorators.

**Solution**: Ensure skill follows Phase 63+ structure:

```
assets/skills/git/
├── scripts/
│   ├── __init__.py
│   ├── status.py      # Has @skill_script decorator
│   └── init.py        # Has @skill_script decorator
└── SKILL.md
```

#### Issue: Command Returns None

**Symptom**: Command fixture exists but returns None

**Cause**: Skill failed to load or command function is None.

**Solution**: Check skill loading:

```python
from agent.core.skill_manager import get_skill_manager

manager = get_skill_manager()
skill = manager.skills.get("git")

if skill:
    print(f"Commands: {list(skill.commands.keys())}")
else:
    print("Skill failed to load")
```

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
