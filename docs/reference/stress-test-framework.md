# Stress Test Framework

> **Status**: Legacy - Phase 9 era documentation
> **Current Approach**: See [Testing Guide](../developer/testing.md) for Phase 35.1 zero-configuration testing

A modular, extensible stress testing framework for MCP servers and agents.

## Overview

The stress test framework provides a standardized way to test performance, stability, and logic depth across different phases of development.

## Architecture

```
mcp-server/tests/              # Outdated path - actual: packages/python/agent/tests/
├── test_stress.py              # Main entry point (just stress-test)
├── test_phase9_stress.py       # Phase 9 standalone entry point
└── stress/
    ├── __init__.py             # Core framework
    ├── core/
    │   └── fixtures.py         # Test data generators
    └── suites/
        └── phase9.py           # Phase 9 test suite
```

> **Note**: The above structure is from Phase 9. The current Phase 35.1 approach uses a Pytest plugin at `packages/python/agent/src/agent/testing/plugin.py` with zero-configuration tests in `assets/skills/*/tests/`.

### Core Components

| Component         | Purpose                                |
| ----------------- | -------------------------------------- |
| `StressConfig`    | Configuration management               |
| `TestRunner`      | Orchestrates test execution            |
| `TestSuite`       | Groups related test cases              |
| `TestCase`        | Individual test definition             |
| `MetricCollector` | Collects performance/stability metrics |
| `Reporter`        | Generates reports in multiple formats  |

## Usage

### Command Line

```bash
# Run all stress test suites
just stress-test

# Run Phase 9 only
python mcp-server/tests/test_phase9_stress.py
```

### Programmatic

```python
from stress import TestRunner, StressConfig, create_runner

# Create runner with custom config
config = StressConfig(
    stress_dir="path/to/test/data",
    max_duration=2.0,
    verbose=True
)
runner = create_runner(config)

# Run specific suite
result = runner.run_suite("Phase9 Code Intelligence")

# Generate report
print(runner.report(result, ReportFormat.TEXT))
```

## Creating a New Test Suite

```python
from stress import TestSuite, TestCase, TestRunner

class Phase10Suite(TestSuite):
    def __init__(self, config):
        super().__init__(
            name="Phase10 Name",
            phase="10",
            description="Description of the suite"
        )
        self.config = config
        self._setup_tests()

    def _setup_tests(self):
        def my_test():
            # Test logic here
            return True

        self.add_test(TestCase(
            name="Test Name",
            test_func=my_test,
            description="Test description",
            tags=["tag1", "tag2"]
        ))

# Register and run
runner = TestRunner()
runner.register_suite(Phase10Suite(config))
result = runner.run_suite("Phase10 Name")
```

## Configuration

```python
@dataclass
class StressConfig:
    # Environment
    stress_dir: Path = Path("mcp-server/tests/stress_data")
    cleanup_after: bool = True
    verbose: bool = True

    # Performance thresholds
    max_duration: float = 2.0  # seconds
    min_throughput: float = 1000.0  # files/second

    # Test parameters
    noise_files: int = 900
    target_files: int = 100
```

## Report Formats

```python
from stress import ReportFormat

# Text report (default)
runner.report(result, ReportFormat.TEXT)

# JSON report (machine-readable)
runner.report(result, ReportFormat.JSON)

# Markdown report (documentation)
runner.report(result, ReportFormat.MARKDOWN)
```

## Metrics Collected

| Metric             | Type        | Description                      |
| ------------------ | ----------- | -------------------------------- |
| `duration`         | PERFORMANCE | Average test execution time      |
| `throughput`       | PERFORMANCE | Operations per second            |
| `stability_passed` | STABILITY   | Number of passed stability tests |
| `stability_failed` | STABILITY   | Number of failed stability tests |

## Phase 9: Code Intelligence Suite

Tests AST-based code intelligence features:

- **Performance Benchmark**: Measures ast-grep search speed
- **Logic Depth Test**: Validates pattern matching accuracy
- **Stability Test**: Checks error handling with malformed inputs

## Best Practices

These practices applied to the Phase 9 stress test framework. For Phase 35.1 testing, see [Testing Guide](../developer/testing.md).

1. **Tag Tests**: Use tags to filter and organize tests
2. **Isolate Tests**: Each test should be independent
3. **Clear Assertions**: Use descriptive failure messages
4. **Measure Metrics**: Collect performance data for trends
5. **Clean Up**: Set `cleanup_after=True` for temporary files

---

## Current Testing (Phase 35.1)

For the current zero-configuration testing approach:

| Aspect            | Legacy (Phase 9)            | Current (Phase 35.1)                         |
| ----------------- | --------------------------- | -------------------------------------------- |
| **Test Location** | `mcp-server/tests/stress/`  | `assets/skills/*/tests/`                     |
| **Configuration** | `conftest.py` per directory | None (Pytest plugin auto-loads)              |
| **Fixtures**      | Manual registration         | Auto-injected by plugin                      |
| **Skill Tests**   | Not supported               | Native via `git`, `knowledge`, etc. fixtures |

**Quick Start (Current)**:

```bash
# Run all skill tests
uv run pytest assets/skills/ -v

# Run specific skill tests
uv run pytest assets/skills/git/tests/ -v
```

See [Testing Guide](../developer/testing.md) for full documentation.
