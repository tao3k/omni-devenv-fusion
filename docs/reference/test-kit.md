# Omni Test Kit

> Comprehensive testing framework for Omni Dev Fusion

## Overview

Omni Test Kit provides a complete testing infrastructure with:

- **Pytest fixtures** for core, git, scanner, and watcher components
- **Testing layer markers** for categorizing tests by execution characteristics
- **Assertion helpers** for common patterns (ToolResponse, skills)
- **Skill test utilities** (builder, tester, suite)
- **Data-driven testing** support

## Quick Start

### Enable in conftest.py

```python
# packages/python/core/tests/conftest.py
pytest_plugins = ["omni.test_kit"]
```

Or import the plugin directly:

```python
pytest_plugins = ["omni.test_kit.plugin"]
```

### Use Fixtures

```python
def test_something(project_root, skills_root, skill_test_suite):
    # All fixtures are automatically available
    assert project_root.exists()
```

## Testing Layer Markers

Mark tests by their execution characteristics:

```python
from omni.test_kit.plugin import unit, integration, cloud, benchmark, stress, e2e

@unit
def test_fast_and_isolated():
    """Unit test - <100ms, mocked dependencies."""
    ...

@integration
async def test_multiple_components(kernel):
    """Integration test - real components, <1s."""
    ...

@cloud
async def test_external_service():
    """Cloud test - requires external services."""
    pytest.skip("Requires LanceDB")
```

### Running by Layer

```bash
# Only unit tests
pytest -m unit

# Integration tests
pytest -m integration

# All tests except cloud
pytest -m "not cloud"

# With cloud tests
pytest --cloud
```

## Assertion Helpers

### Basic Assertions

```python
from omni.test_kit.asserts import (
    assert_equal,
    assert_in,
    assert_length,
    assert_true,
    assert_is_none,
)

assert_equal(expected, actual)
assert_in(item, container)
assert_length(container, expected_len)
```

### ToolResponse Assertions

```python
from omni.test_kit.asserts import (
    assert_response_ok,
    assert_response_error,
    assert_has_error,
    assert_response_data,
)

# Success response
response = ToolResponse.success(data={"result": "ok"})
assert_response_ok(response)

# Error response
error_response = ToolResponse.error(message="Not found", code="3001")
assert_has_error(error_response, expected_code="3001")
```

### Skill Assertions

```python
from omni.test_kit.asserts import (
    assert_skill_loaded,
    assert_skill_has_permission,
    assert_skill_has_command,
)

assert_skill_loaded(skill_info, expected_name="git")
assert_skill_has_permission(skill_info, "filesystem:read")
```

## Skill Test Builder

Create test skills programmatically:

```python
from omni.test_kit.fixtures import SkillTestBuilder

builder = SkillTestBuilder("my_test_skill")
builder.with_metadata(
    version="1.0.0",
    description="A test skill",
    routing_keywords=["test", "demo"],
    authors=["Author <email>"],
    permissions=["filesystem:read"],
)
builder.with_script("commands.py", """
def my_command():
    return "Hello"
""")

skill_path = builder.create("/tmp/test_skills")
```

## Skill Test Suite

Manage multiple test skills:

```python
from omni.test_kit.fixtures import SkillTestSuite

with SkillTestSuite(tempfile.mkdtemp()) as suite:
    suite.create_skill(
        "skill_one",
        description="First skill",
        routing_keywords=["one"],
    )
    suite.create_skill(
        "skill_two",
        version="2.0.0",
        routing_keywords=["two"],
    )

    skills = suite.scan_all()
    assert len(skills) == 2
```

## Skill Tester

Execute skill commands in tests:

```python
import pytest
from omni.test_kit.fixtures import SkillTester

@pytest.fixture
async def tester(skill_tester):
    return skill_tester

async def test_skill_execution(tester):
    result = await tester.run("git", "status")
    assert result.success
    assert result.output is not None
```

## Decorators

### Data-Driven Testing

```python
from omni.test_kit.decorators import data_driven, omni_skill

# Mark test as data-driven
@data_driven("test_cases.json")
def test_something(case):
    """Runs once per test case in test_cases.json."""
    assert case.expected == case.input

# Mark test for specific skill
@omni_skill("git")
def test_git_feature():
    ...
```

## Available Fixtures

### Core Fixtures

| Fixture              | Description                               |
| -------------------- | ----------------------------------------- |
| `project_root`       | Project root directory (via git toplevel) |
| `skills_root`        | Skills directory (assets/skills)          |
| `config_dir`         | Config directory                          |
| `cache_dir`          | Cache directory                           |
| `clean_settings`     | Fresh Settings instance                   |
| `mock_agent_context` | Mock agent context                        |
| `test_tracer`        | TestTracer for debugging                  |

### Git Fixtures

| Fixture           | Description                |
| ----------------- | -------------------------- |
| `temp_git_repo`   | Temporary git repository   |
| `git_repo`        | Git repository fixture     |
| `git_test_env`    | Git test environment       |
| `gitops_verifier` | GitOps verification helper |

### Scanner Fixtures

| Fixture                 | Description                 |
| ----------------------- | --------------------------- |
| `skill_test_suite`      | SkillTestSuite instance     |
| `skill_directory`       | Single test skill directory |
| `multi_skill_directory` | Multiple skills directory   |
| `skill_tester`          | SkillTester async fixture   |

### Watcher Fixtures

| Fixture                   | Description               |
| ------------------------- | ------------------------- |
| `mock_watcher_indexer`    | Mock watcher indexer      |
| `temp_skill_dir`          | Temporary skill directory |
| `sample_skill_script`     | Sample skill script       |
| `sample_skill_with_tools` | Sample skill with tools   |

## Examples

### Complete Unit Test

```python
"""test_responses.py"""
import pytest
from omni.test_kit.plugin import unit
from omni.test_kit.asserts import assert_response_ok
from omni.core.responses import ToolResponse

@unit
def test_success_response():
    response = ToolResponse.success(data={"key": "value"})
    assert_response_ok(response)
```

### Integration Test with Fixtures

```python
"""test_skill_loader.py"""
import pytest
from omni.test_kit.plugin import integration
from omni.test_kit.fixtures import SkillTestSuite

@integration
async def test_skill_loading():
    with SkillTestSuite(tempfile.mkdtemp()) as suite:
        suite.create_skill("test_skill", description="Test")
        skills = suite.scan_all()
        assert len(skills) == 1
```

### Parameterized Test

```python
"""test_math.py"""
import pytest
from omni.test_kit.plugin import unit
from omni.test_kit.asserts import assert_equal

@unit
@pytest.mark.parametrize("a,b,expected", [
    (1, 1, 2),
    (2, 3, 5),
    (10, 5, 15),
])
def test_addition(a, b, expected):
    assert_equal(a + b, expected)
```

## Configuration

### pytest.ini

```ini
[tool:pytest]
markers =
    unit: Fast, isolated tests
    integration: Multi-component tests
    cloud: External service tests
    benchmark: Performance tests
    stress: Long-running tests
    e2e: End-to-end tests

addopts =
    -v
    --tb=short
```

## Best Practices

1. **Mark all tests appropriately**: Use `@unit`, `@integration`, `@cloud` markers
2. **Use assertion helpers**: They provide clear error messages
3. **Create reusable fixtures**: Add to conftest.py for common setup
4. **Isolate cloud tests**: Mark with `@cloud` and skip by default
5. **Use SkillTestBuilder**: Create consistent test skills

## Related Files

- `packages/python/test-kit/src/omni/test_kit/plugin.py` - Pytest plugin
- `packages/python/test-kit/src/omni/test_kit/fixtures/` - Fixtures
- `packages/python/test-kit/src/omni/test_kit/asserts.py` - Assertions
- `packages/python/test-kit/src/omni/test_kit/decorators.py` - Decorators
- `docs/architecture/testing-layers.md` - Testing layer strategy
