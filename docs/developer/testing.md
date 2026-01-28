# Omni-Dev-Fusion Testing Guide

> Trinity Architecture Test System - Foundation, Core, MCP-Server
> Last Updated: 2026-01-25

---

## Overview

### Trinity Test Architecture

```
packages/python/
├── foundation/tests/              # 46 tests - Settings, Config, GitOps, Skills Path
├── core/tests/                    # 49 tests - Router, Script Loader, Indexer, Skills
├── mcp-server/tests/              # 42 tests - Transport, Types, Server
└── agent/tests/                   # CLI tests, skill management
assets/skills/*/tests/             # 263 skill tests (11 skills)
```

### Test Status Summary

| Package    | Passing | Skipped | Failing | Status      |
| ---------- | ------- | ------- | ------- | ----------- |
| Foundation | 46      | 0       | 0       | DONE        |
| Core       | 49      | 0       | 0       | DONE        |
| MCP-Server | 42      | 0       | 0       | DONE        |
| Agent      | 19      | 0       | 0       | DONE        |
| Skills     | 263     | 2       | 0       | DONE        |
| **Total**  | **419** | **2**   | **0**   | **HEALTHY** |

---

## Running Tests

### Package Tests (Parallel Execution Enabled)

Tests run in parallel with timeout protection (300s default):

```bash
# Foundation tests (settings, config, gitops)
uv run pytest packages/python/foundation/tests/ -q

# Core tests (router, script loader, indexer, skills)
uv run pytest packages/python/core/tests/ -q

# MCP-Server tests (transport, server, types)
uv run pytest packages/python/mcp-server/tests/ -q

# Agent CLI tests
uv run pytest packages/python/agent/tests/ -q
```

### All Package Tests Combined

```bash
# Using just command
just test
```

### Skill Tests (via omni CLI)

```bash
# Test single skill
uv run omni skill test git

# Test all skills with tests/
uv run omni skill test --all
```

### With Coverage Report

```bash
# Terminal coverage summary
uv run pytest --cov=omni --cov-report=term-missing

# Generate HTML report
uv run pytest --cov=omni --cov-report=html
# Open .htmlcov/index.html in browser

# Per-module coverage
uv run pytest --cov=omni.foundation --cov-report=term
```

### Custom Timeout

```bash
# Quick test (60s timeout)
uv run pytest --timeout=60

# No timeout
uv run pytest --timeout=0

# Per-test timeout marker
pytest -v --timeout=30 test_slow_operation.py
```

---

## Test Structure

### Foundation Tests (`packages/python/foundation/tests/`)

| File                  | Tests | Purpose                                 |
| --------------------- | ----- | --------------------------------------- |
| `test_settings.py`    | 15    | Settings singleton, get(), YAML parsing |
| `test_config.py`      | 10    | Config class, directory resolution      |
| `test_gitops.py`      | 11    | get_project_root(), ProjectPaths        |
| `test_skills_path.py` | 10    | Skill utility functions                 |

**Key Fixtures**: None (pure unit tests with mocked imports)

### Core Tests (`packages/python/core/tests/`)

| File                    | Tests               | Purpose                                   |
| ----------------------- | ------------------- | ----------------------------------------- |
| `test_router/`          | Router logic        | Hive router, semantic router              |
| `test_script_loader.py` | Script loading      | Universal skill script discovery          |
| `test_indexer.py`       | 7 passed, 5 skipped | Skill indexing (requires RustVectorStore) |

**Indexer Tests**: Uses `@indexing_available` marker to skip when RustVectorStore/embedding unavailable.

### MCP-Server Tests (`packages/python/mcp-server/tests/`)

| File           | Tests | Purpose                                 |
| -------------- | ----- | --------------------------------------- |
| `unit/`        | 30    | Type definitions, transport, interfaces |
| `integration/` | 12    | SSE transport, server lifecycle         |

**Key Fixtures**:

- `unused_port`: Get available port for testing servers
- `server_url`: Generate server URL
- `mock_handler`: Mock MCP request handler

---

## Writing Tests

### Foundation Test Pattern

```python
"""Tests for omni.foundation.config.settings module."""

import pytest


class TestSettingsClass:
    """Test the Settings singleton class."""

    def test_singleton_pattern(self):
        """Test that Settings is a singleton."""
        from omni.foundation.config.settings import Settings

        # Reset singleton for test
        Settings._instance = None
        Settings._loaded = False

        settings1 = Settings()
        settings2 = Settings()

        assert settings1 is settings2
```

### Core Async Test Pattern

```python
"""Tests for omni.core.skills.discovery module."""

import pytest
from omni.core.skills.discovery import UniversalSkillDiscovery


class TestUniversalSkillDiscovery:
    """Test skill discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_skills_empty_dir(self):
        """Test discovering skills in empty directory."""
        discovery = UniversalSkillDiscovery()
        skills = await discovery.discover_skills("/tmp/empty")

        assert skills == []
```

### MCP-Server Test Pattern

```python
"""Tests for omni.mcp.transport module."""

import pytest
from omni.mcp.transport.stdio import StdioTransport


class TestStdioTransport:
    """Test stdio transport."""

    @pytest.mark.asyncio
    async def test_create_transport(self):
        """Test creating stdio transport."""
        transport = StdioTransport()
        assert transport is not None
```

---

## Conditional Test Skipping

### Indexer Tests (RustVectorStore + Embedding)

For tests requiring RustVectorStore and embedding service:

```python
import pytest
from omni.core.router.indexer import SkillIndexer, IndexedSkill


def _is_indexing_available() -> bool:
    """Check if skill indexing is fully available."""
    try:
        from omni.foundation.bridge import RustVectorStore
        store = RustVectorStore(":memory:", 1536)

        from omni.foundation.services.embedding import get_embedding_service
        service = get_embedding_service()
        _ = service.embed("test")
        return True
    except Exception:
        return False


indexing_available = pytest.mark.skipif(
    not _is_indexing_available(),
    reason="Skill indexing unavailable (Rust bridge or embedding service not configured)"
)


class TestSkillIndexerIndexing:
    """Test skill indexing functionality."""

    @pytest.mark.asyncio
    @indexing_available
    async def test_index_skills_single_skill(self):
        """Test indexing a single skill."""
        indexer = SkillIndexer()
        skills = [{"name": "git", "description": "Git operations"}]
        count = await indexer.index_skills(skills)
        assert count >= 1
```

---

## Pytest Configuration

The project uses pytest 9.0+ with the following configuration in `pyproject.toml`:

```toml
[tool.pytest]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
strict = true  # Enable strict mode
timeout = 300  # Default timeout (5 minutes)

# Parallel execution with resource limits
addopts = [
    "--timeout=300",
    "-n", "auto",           # Auto-detect CPU cores
    "--maxprocesses=4",     # Limit to 4 processes
    "-p", "no:randomly",    # Deterministic order
]
```

### Key Features

| Feature                | Description                                            |
| ---------------------- | ------------------------------------------------------ |
| **Parallel Execution** | Tests run in parallel (`-n auto`) for faster execution |
| **Timeout Protection** | 300s default prevents hung tests                       |
| **Strict Mode**        | Catches misconfigured markers and xfail                |
| **Coverage**           | Integrated with `pytest-cov`                           |
| **Import Mode**        | Uses `importlib` for implicit namespace packages       |

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["omni"]
branch = true
parallel = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
show_missing = true
```

---

## Known Issues

### 1. Pytest ImportPathMismatchError (RESOLVED)

**Symptom**: Previously showed `ImportPathMismatchError` with multiple `conftest.py` files

**Solution**: Use `--import-mode=importlib` in pytest configuration

**Status**: ✅ RESOLVED - Tests can now run together without conflicts

### 2. Indexer Tests Skipped Without RustVectorStore

**Symptom**: `test_index_skills_*` tests show as skipped

**Cause**: RustVectorStore or embedding service not configured

**Solution**: Tests use `@indexing_available` marker to skip gracefully

**Status**: Expected behavior - tests skipped when dependencies unavailable

### 3. Skill Tests with Implicit Namespace Packages

**Symptom**: Tests in `assets/skills/*/tests/` fail to import without `__init__.py`

**Cause**: Python 3.13 implicit namespace packages require special pytest handling

**Solution**: Use `--import-mode=importlib` flag

**Status**: ✅ RESOLVED - Configuration added to `omni skill test --all`

---

## Rust Tests

Located in `packages/rust/crates/omni-*/src/*.rs` with inline `#[cfg(test)]` modules.

### Running Rust Tests

```bash
# Run all Rust tests
cargo test --workspace

# Run specific crate tests
cargo test -p omni-vector
cargo test -p omni-scanner
cargo test -p omni-tags
```

### Rust Test Status

| Crate        | Tests | Status  |
| ------------ | ----- | ------- |
| omni-vector  | 35    | PASSING |
| omni-scanner | -     | TODO    |
| omni-tags    | -     | TODO    |

---

## Adding New Tests

### For Foundation Package

1. Create test file in `packages/python/foundation/tests/`
2. Use direct imports from `omni.foundation.*`
3. Reset singletons in test setup if needed

### For Core Package

1. Create test file in `packages/python/core/tests/units/`
2. Use async tests with `@pytest.mark.asyncio`
3. Add conditional skipping for optional dependencies

### For MCP-Server Package

1. Create test file in `packages/python/mcp-server/tests/unit/` or `integration/`
2. Use fixtures from `packages/python/mcp-server/tests/conftest.py`
3. Mock server components for unit tests

---

## CI/CD

### GitHub Actions Workflow

Tests run on every push to `main` branch with parallel execution and coverage:

```yaml
jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest packages/python/foundation/tests/ -q
      - run: uv run pytest packages/python/core/tests/ -q
      - run: uv run pytest packages/python/mcp-server/tests/ -q
      - run: uv run pytest packages/python/agent/tests/ -q
      - run: uv run omni skill test --all
      - run: cargo test --workspace
      # Optional: Coverage report
      - run: uv run pytest --cov=omni --cov-report=term-missing
```

---

## Related Documentation

- [Trinity Architecture](../../explanation/trinity-architecture.md)
- [Skills System](../../skills.md)
- [Project Execution Standard](../../reference/project-execution-standard.md)
- [Justfile](../../justfile)
