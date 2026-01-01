# Spec: Modular Stress Test Framework

> **Status**: Approved
> **Complexity**: L2
> **Owner**: @omni-coder

## 1. Context & Goal (Why)

_A modular, extensible stress testing framework for MCP servers and agents, enabling systematic performance, stability, and logic depth testing across all development phases._

- **Goal**: Provide a standardized, pluggable infrastructure for stress testing that can scale from Phase 9 (Code Intelligence) to Phase 10+ (Hive Architecture) without major refactoring.
- **User Story**: As a developer working on Phase 10, I want a stress test framework that I can easily extend with new suites and collectors, so I don't have to rebuild testing infrastructure for each phase.

## 2. Architecture & Interface (What)

_Defines the framework contract for stress testing infrastructure._

### 2.1 File Changes

#### New Files

- `mcp-server/tests/stress/__init__.py`: Core framework (Config, Runner, Collectors, Reporters)
- `mcp-server/tests/test_stress.py`: Main entry point (`just stress-test`)
- `mcp-server/tests/test_phase9_stress.py`: Phase 9 standalone entry point
- `docs/reference/stress-test-framework.md`: User documentation

#### Modified Files

- `justfile`: Added `stress-test` command

### 2.2 Data Structures / Schema

```python
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable

class ResultStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

class MetricType(Enum):
    DURATION = "duration"
    MEMORY = "memory"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    COUNT = "count"
    RATIO = "ratio"

class ReportFormat(Enum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"

@dataclass
class StressConfig:
    stress_dir: Path = Path("mcp-server/tests/stress_data")
    cleanup_after: bool = True
    verbose: bool = True
    max_duration: float = 2.0
    min_throughput: float = 1000.0
    noise_files: int = 900
    target_files: int = 100

@dataclass
class Metric:
    name: str
    value: float
    unit: str
    metric_type: MetricType
    tags: dict = field(default_factory=dict)

@dataclass
class TestResult:
    name: str
    suite: str
    status: ResultStatus
    duration: float
    message: str = ""
    error: Optional[str] = None

@dataclass
class SuiteResult:
    name: str
    phase: str
    tests: List[TestResult]
    metrics: List[Metric]
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
```

### 2.3 API Signatures (Pseudo-code)

```python
class TestRunner:
    """Main orchestrator for stress test execution."""
    def __init__(self, config: StressConfig = None)
    def register_suite(self, suite: TestSuite) -> None
    def run_suite(self, name: str) -> SuiteResult
    def run_all(self) -> Dict[str, SuiteResult]
    def report(self, result: SuiteResult, format: ReportFormat) -> str

class TestSuite:
    """Collection of related test cases."""
    def __init__(self, name: str, phase: str, description: str = "")
    def add_test(self, test: TestCase) -> None
    def run(self, collector: MetricCollector = None) -> SuiteResult

class TestCase:
    """Individual test definition."""
    def __init__(
        self,
        name: str,
        test_func: Callable[[], Any],
        description: str = "",
        tags: List[str] = None,
        timeout: float = 30.0
    )
    def run(self) -> TestResult

class MetricCollector(ABC):
    """Base class for metric collectors."""
    def collect(self, context: dict) -> List[Metric]
    def reset(self) -> None

# Concrete collectors
class PerformanceCollector(MetricCollector)
class StabilityCollector(MetricCollector)
class MemoryCollector(MetricCollector)
class CompositeCollector(MetricCollector)

# Reporters
class Reporter(ABC)
class TextReporter(Reporter)
class JSONReporter(Reporter)
class MarkdownReporter(Reporter)
```

## 3. Implementation Plan (How)

### Phase 1: Core Infrastructure

1. [x] **Define core data structures** (TestResult, SuiteResult, Metric, StressConfig)
2. [x] **Implement TestRunner** with suite registration and execution
3. [x] **Create base TestSuite and TestCase classes**
4. [x] **Add metric collectors** (Performance, Stability, Memory)

### Phase 2: Reporting System

1. [x] **Implement Reporter base class**
2. [x] **Create TextReporter** for console output
3. [x] **Create JSONReporter** for CI/CD integration
4. [x] **Create MarkdownReporter** for documentation

### Phase 3: Phase 9 Integration

1. [x] **Implement Phase9Suite** with Performance, Logic, Stability tests
2. [x] **Create test data generators** in fixtures.py
3. [x] **Add justfile command** for easy execution

### Phase 4: Extensibility

1. [x] **Define plugin interface** for custom collectors
2. [x] **Add configuration loading** from YAML/JSON
3. [x] **Create documentation** at docs/reference/

## 4. Verification Plan (Test)

_How do we know it works? Matches `agent/standards/feature-lifecycle.md` requirements._

### 4.1 Functional Tests

- [x] **Framework initialization**: TestRunner creates successfully
- [x] **Suite registration**: Suites can be registered and listed
- [x] **Test execution**: Tests run and return valid results
- [x] **Report generation**: All three formats produce valid output
- [x] **Phase 9 suite**: All 3 tests pass (Performance, Logic, Stability)

### 4.2 Performance Tests

- [x] **Benchmark performance**: ast-grep search < 2s for 1000 files
- [x] **Throughput validation**: > 1000 files/second
- [x] **Memory usage**: No memory leaks during test execution

### 4.3 Integration Tests

- [x] **CLI integration**: `just stress-test` runs successfully
- [x] **Import validation**: All modules import without errors
- [x] **Syntax validation**: All Python files compile successfully

### 4.4 Extensibility Tests

- [x] **Custom suite**: New suites can be registered and executed
- [x] **Custom collector**: Custom metric collectors integrate correctly
- [x] **Configuration**: Config loading from file works

## 5. Design Decisions

| Decision                   | Pros                         | Cons                                 |
| -------------------------- | ---------------------------- | ------------------------------------ |
| Plugin-based collectors    | Easy to extend, modular      | Initial complexity                   |
| CompositeCollector pattern | Combines multiple collectors | Slight overhead                      |
| Enum-based report formats  | Type-safe, extensible        | Requires enum update for new formats |
| Callable-based tests       | Simple API, flexible         | Less structure than class-based      |
| Global config singleton    | Easy access                  | Potential threading issues           |

## 6. Usage Examples

### Basic Usage

```bash
# Run all stress tests
just stress-test

# Run with verbose output
just stress-test 2>&1 | cat

# Check exit code
just stress-test && echo "All passed"
```

### Programmatic Usage

```python
from stress import TestRunner, StressConfig, Phase9Suite

# Create runner
config = StressConfig(max_duration=1.0)
runner = TestRunner(config)

# Run Phase 9 suite
result = runner.run_suite("Phase9 Code Intelligence")

# Get JSON report
json_report = runner.report(result, ReportFormat.JSON)
```

### Creating a New Suite

```python
from stress import TestSuite, TestCase

class Phase10Suite(TestSuite):
    def __init__(self, config):
        super().__init__(
            name="Phase10 Hive Architecture",
            phase="10",
            description="Tests for microservices architecture"
        )
        self.add_test(TestCase(
            name="Service Health Check",
            test_func=self._test_health,
            tags=["stability", "microservice"]
        ))

    def _test_health(self):
        # Implement health check test
        return True
```

## 7. Roadmap

| Phase    | Status  | Description                               |
| -------- | ------- | ----------------------------------------- |
| Phase 9  | Done    | Code Intelligence (ast-grep) testing      |
| Phase 10 | Planned | Hive Architecture (microservices) testing |
| Phase 11 | TBD     | Advanced load balancing tests             |
| Future   | TBD     | Distributed stress testing                |

## 8. Related Documentation

- **Reference**: `docs/reference/stress-test-framework.md`
- **Tutorials**: Coming with Phase 10
- **API Docs**: Inline docstrings in `mcp-server/tests/stress/__init__.py`
