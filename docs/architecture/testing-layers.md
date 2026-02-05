# Testing Layer Strategy

> Omni-Dev-Fusion Testing Architecture

## Overview

The testing layer strategy implements a systematic approach to categorizing and executing tests by their characteristics and requirements. This ensures fast local development while supporting comprehensive CI/CD testing.

## Test Layers

| Layer           | Marker        | Duration | Dependencies      | Execution          |
| --------------- | ------------- | -------- | ----------------- | ------------------ |
| **Unit**        | `unit`        | < 100ms  | None (mocked)     | Default            |
| **Integration** | `integration` | < 1s     | Real components   | `-m integration`   |
| **Cloud**       | `cloud`       | Variable | External services | `--cloud`          |
| **Benchmark**   | `benchmark`   | Variable | None              | `--benchmark-only` |
| **Stress**      | `stress`      | Minutes  | Resources         | `-m stress`        |
| **E2E**         | `e2e`         | Minutes  | Complete system   | `-m e2e`           |

## Quick Start

### Run Unit Tests (Default)

```bash
# Fast local development
pytest packages/python/core/tests/units/ -v

# Or with pytest.ini configuration
pytest -m unit
```

### Run Integration Tests

```bash
# Tests with real components
pytest packages/python/core/tests/ -m integration -v
```

### Run All Tests (CI)

```bash
# Include cloud tests
pytest --cloud -v

# Or explicitly include all layers
pytest -m "unit or integration or cloud or benchmark or stress or e2e" -v
```

### Skip Slow Tests

```bash
# Only fast tests
pytest --fast

# Exclude specific layers
pytest -m "not cloud and not stress and not e2e" -v
```

## Markers

### Unit Tests

Fast, isolated tests with mocked dependencies.

```python
from omni.core.testing.layers import unit

@unit
def test_something():
    """This is a unit test."""
    ...
```

### Integration Tests

Tests involving multiple real components.

```python
from omni.core.testing.layers import integration

@integration
async def test_component_interaction(kernel):
    """Integration test using real kernel."""
    ...
```

### Cloud Tests

Tests requiring external services (skipped locally by default).

```python
from omni.core.testing.layers import cloud

@cloud
async def test_remote_service():
    """Requires external service."""
    ...
```

Run with: `pytest --cloud`

### Skip Helpers

```python
from omni.core.testing.layers import skip_if_cloud

@skip_if_cloud(reason="External API required")
def test_external_api():
    """Skip this test unless --cloud is set."""
    ...
```

## Pytest Configuration

### pytest.ini

```ini
[tool:pytest]
markers =
    unit: Fast, isolated tests with mocked dependencies
    integration: Tests with multiple real components
    cloud: Tests requiring external services (CI only)
    benchmark: Performance benchmarking tests
    stress: Long-running stress/load tests
    e2e: End-to-end user workflow tests

addopts =
    -v
    --tb=short
    -p no:warnings
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast, isolated tests with mocked dependencies",
    "integration: Tests with multiple real components",
    "cloud: Tests requiring external services (CI only)",
    "benchmark: Performance benchmarking tests",
    "stress: Long-running stress/load tests",
    "e2e: End-to-end user workflow tests",
]
```

## Directory Structure

```
packages/python/core/tests/
├── conftest.py              # Shared fixtures
├── units/                   # Unit tests
│   ├── test_*.py
│   └── test_*.py
├── integration/             # Integration tests
│   ├── test_*.py
│   └── conftest.py
├── cloud/                   # Cloud/external tests
│   ├── test_*.py
│   └── conftest.py
├── benchmarks/              # Performance benchmarks
│   └── test_*.py
├── stress/                  # Stress tests
│   └── test_*.py
└── e2e/                     # End-to-end tests
    └── test_*.py
```

## CI/CD Pipeline

```yaml
name: Tests

on: [push, pull_request]

jobs:
  # Fast unit tests - runs on every PR
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -m unit -v

  # Integration tests - runs on merge to main
  integration-test:
    runs-on: ubuntu-latest
    needs: unit-test
    steps:
      - uses: actions/checkout@v4
      - run: pytest -m integration -v

  # Full test suite - runs on release
  full-test:
    runs-on: ubuntu-latest
    needs: integration-test
    steps:
      - uses: actions/checkout@v4
      - run: pytest --cloud -v
```

## Best Practices

### 1. Mark New Tests Appropriately

```python
# Good: Properly marked
@unit
def test_simple_function():
    ...

# Good: Integration test with real dependency
@integration
async def test_database_query():
    ...
```

### 2. Keep Unit Tests Fast

- Mock all external calls
- Target < 100ms per test
- Use in-memory fixtures

### 3. Isolate Cloud Tests

```python
# Use fixtures to isolate cloud dependencies
@pytest.fixture
def mock_external_service(monkeypatch):
    """Mock external service for non-cloud tests."""
    monkeypatch.setattr("requests.get", mock_get)

@integration
def test_with_mocked_service(mock_external_service):
    """This test runs in integration mode but mocks external calls."""
    ...
```

### 4. Use Skip Helpers for Optional Dependencies

```python
from omni.core.testing.layers import skip_if_cloud

@skip_if_cloud(reason="Requires OpenAI API key")
def test_openai_feature():
    """Skipped locally, runs in CI with API keys."""
    ...
```

## Related Files

- `packages/python/core/src/omni/core/testing/layers.py` - Marker definitions
- `packages/python/core/src/omni/core/testing/__init__.py` - Public API
- `packages/python/core/tests/conftest.py` - Shared fixtures
- `packages/python/core/pyproject.toml` - Pytest configuration
