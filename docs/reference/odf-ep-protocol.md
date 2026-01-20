# ODF-EP (Python Zenith) Engineering Protocol

> Universal Engineering Standard for Python/Rust Projects
> Version: v2.0 | Last Updated: 2026-01-18

---

## Table of Contents

- [Overview](#overview)
- [Core Philosophy](#core-philosophy)
- [Code Style](#code-style)
- [Naming Conventions](#naming-conventions)
- [Module Design](#module-design)
- [Error Handling](#error-handling)
- [Testing Standards](#testing-standards)
- [Documentation](#documentation)
- [Git Workflow](#git-workflow)
- [TL;DR Cheat Sheet](#tldr-cheat-sheet)

---

## Overview

ODF-EP is a **universal engineering standard** for Python/Rust projects. It defines:

- **How to write code**: Style, patterns, conventions
- **How to organize**: Module boundaries, dependencies
- **How to test**: Standards, coverage, patterns
- **How to document**: Docstrings, comments, decisions

### Core Philosophy

1. **Explicit over Implicit**: Configuration drives behavior
2. **Single Source of Truth**: One place for each value/path
3. **Composition over Inheritance**: Functional patterns preferred
4. **Fail Fast**: Validate early, fail loudly
5. **Document Decisions**: Explain why, not just what

---

## Code Style

### Python Standards

| Rule                | Description                                     |
| ------------------- | ----------------------------------------------- |
| Type Hints          | All functions must have return type annotations |
| Async-First         | Use `async/await` for I/O operations            |
| No Mutable Defaults | Use `None` and initialize in body               |
| Docstrings          | Google-style for all public functions           |

### Type Hints

```python
# GOOD - Complete type annotations
def calculate_score(additions: int, deletions: int) -> float:
    """Calculate a quality score from diff metrics."""
    return (additions + deletions) / 100.0

# GOOD - Union types for Python 3.10+
def process_value(value: int | str) -> str:
    """Convert value to string."""
    return str(value)

# BAD - Missing return type
def calculate_score(additions: int, deletions: int):
    return (additions + deletions) / 100.0
```

### Async-First

```python
# GOOD - Async for I/O
async def fetch_data(url: str) -> dict:
    """Fetch JSON data from URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# BAD - Blocking I/O in async context
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

### No Mutable Defaults

```python
# GOOD - None default, initialize in body
def create_tool(name: str, config: dict | None = None) -> Tool:
    """Create a tool instance."""
    config = config or {}
    return Tool(name=name, **config)

# BAD - Mutable default argument
def create_tool(name: str, config: dict = {}) -> Tool:
    return Tool(name=name, **config)
```

### Import Order

```python
# 1. Standard library
import asyncio
from pathlib import Path
from typing import Any

# 2. Third party
import aiohttp
from pydantic import BaseModel

# 3. Local - absolute imports
from module_a import ClassA
from package_b import function_b
```

---

## Naming Conventions

| Element           | Convention                         | Example                      |
| ----------------- | ---------------------------------- | ---------------------------- |
| Project name      | kebab-case                         | `my-project`                 |
| Python package    | snake_case                         | `my_package`                 |
| Python module     | snake_case                         | `skill_manager.py`           |
| Python class      | PascalCase                         | `SkillManager`               |
| Function/Variable | snake_case                         | `get_setting()`              |
| Constant          | UPPER_SNAKE_CASE                   | `DEFAULT_TIMEOUT`            |
| Private function  | snake_case with leading underscore | `_internal_helper()`         |
| Type alias        | PascalCase                         | `SkillMap: dict[str, Skill]` |
| Config key        | dot notation                       | `mcp.timeout`                |

### Examples

```python
# Package/module names
from processing_pipeline import DataProcessor  # snake_case module
from utils import Validator  # PascalCase class

# Functions/variables
def calculate_metrics() -> dict:
    """Calculate and return metrics."""
    cache_file = get_cache_path()  # snake_case
    return {"value": 42}

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 30

# Config keys (dot notation in YAML)
# mcp:
#   timeout: 30
#   retry_count: 3
```

---

## Module Design

### Single Responsibility Principle

Each module/class should have **one clear purpose**.

```python
# GOOD - Focused modules
# file: utils/path_resolver.py
def resolve_path(base: Path, relative: str) -> Path:
    """Resolve relative path against base."""
    return base / relative

# file: config/settings_loader.py
def load_settings(config_path: Path) -> dict:
    """Load settings from YAML file."""
    return yaml.safe_load(config_path.read_text())

# BAD - God module
# file: utils.py
def resolve_path(...): ...
def load_settings(...): ...
def validate_input(...): ...
def format_output(...): ...
```

### Small Functions

Prefer small, focused functions (< 50 lines).

```python
# GOOD - Focused, small function
def validate_url(url: str) -> bool:
    """Check if URL is valid."""
    if not url:
        return False
    return url.startswith(("http://", "https://"))

# BAD - Too long, doing too much
def process_repository(url: str, options: dict) -> Result:
    """Clone, configure, validate, and return repo."""
    # 100+ lines doing everything
```

### Import Rules

| Pattern                         | Allowed | Example                             |
| ------------------------------- | ------- | ----------------------------------- |
| Absolute imports                | Yes     | `from package.module import func`   |
| Relative imports (same package) | Yes     | `from .utils import helper`         |
| Deep relative imports           | No      | `from ..common.utils import helper` |
| Wildcard imports                | No      | `from module import *`              |

```python
# GOOD - Explicit absolute imports
from config.settings import get_setting
from utils.paths import resolve_path

# GOOD - Local relative imports
from .validation import validate_input
from .constants import DEFAULT_TIMEOUT

# BAD - Deep relative (confusing, hard to trace)
from ..common.settings import get_setting

# BAD - Wildcard import
from utils import *
```

### Dependency Flow

**Dependencies flow inward**: Outer layers depend on inner layers.

```
         ┌─────────────────┐
         │  CLI / Entry    │  ← Depends on Core
         ├─────────────────┤
         │     Core        │  ← Depends on Common/Utils
         ├─────────────────┤
         │  Common/Utils   │  ← No dependencies inward
         └─────────────────┘
```

Never: Common importing from Core, or Core importing from CLI.

---

## Error Handling

### Principles

1. **Fail Fast**: Validate inputs early
2. **Fail Loudly**: Use exceptions, not silent failures
3. **Context Matters**: Include relevant information in errors

### Patterns

```python
# Input validation
def git_clone(url: str, target_dir: Path | None = None) -> str:
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://", "git@")):
        raise ValueError(f"Invalid git URL: {url}")
    # ...

# Wrap external calls with retries
async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            return await fetch_url(url)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed after {max_retries} attempts: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    raise RuntimeError("Unexpected error in fetch_with_retry")

# Rich error context
def parse_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Project root: {get_project_root()}"
        )
    # ...
```

### Error Categories

| Category         | Exception Type       | Recovery             |
| ---------------- | -------------------- | -------------------- |
| Invalid input    | `ValueError`         | Caller fixes input   |
| Missing resource | `FileNotFoundError`  | Caller provides path |
| External failure | `RuntimeError`       | Retry or escalate    |
| Configuration    | `ConfigurationError` | Check settings       |
| Security         | `SecurityError`      | Block and log        |

---

## Testing Standards

### Unit Tests REQUIRED

**Every feature change MUST have corresponding tests:**

| Change         | Action                     |
| -------------- | -------------------------- |
| Add feature    | Add unit/integration tests |
| Remove feature | Remove corresponding tests |
| Refactor code  | Update tests accordingly   |
| Fix bug        | Add regression test        |

### Test Structure

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Full-stack tests
└── conftest.py        # Pytest configuration
```

### Test Principles

1. **No path hacking** - Use project utilities
2. **No for loops** - Use `@pytest.mark.parametrize`
3. **No hardcoded values** - Use factories or fixtures

```python
# GOOD - Parametrized test
@pytest.mark.parametrize("input,expected", [
    ("https://github.com", True),
    ("invalid-url", False),
])
def test_validate_url(input: str, expected: bool):
    assert validate_url(input) == expected

# BAD - For loop
for input, expected in test_cases:
    assert validate_url(input) == expected
```

### Coverage Guidelines

| Component     | Minimum Coverage |
| ------------- | ---------------- |
| Core logic    | 90%              |
| Utilities     | 95%              |
| Configuration | 100%             |

---

## Documentation

### Docstrings

Use Google-style docstrings for all public functions.

```python
def calculate_score(
    additions: int,
    deletions: int,
    files_changed: int,
    scope_weight: dict[str, float] | None = None,
) -> tuple[float, str]:
    """Calculate a score for commit quality based on change metrics.

    This function evaluates commit quality by analyzing the diff metrics
    and providing both a numeric score and a qualitative assessment.

    Args:
        additions: Number of lines added
        deletions: Number of lines deleted
        files_changed: Number of files modified
        scope_weight: Optional dict mapping scope names to weight multipliers

    Returns:
        Tuple of (score: float 0-100, assessment: str)

    Raises:
        ValueError: If any metric is negative

    Example:
        >>> score, assessment = calculate_score(50, 20, 3)
        >>> print(f"Score: {score}, Assessment: {assessment}")
    """
    if additions < 0 or deletions < 0 or files_changed < 0:
        raise ValueError("Metrics cannot be negative")
    # ...
```

### Inline Comments

Explain **why**, not **what**.

```python
# GOOD - Explains why
# Use ID-based deletion, not LIKE with path strings
# because _ in paths would be interpreted as wildcard
results = table.scan(filter_expr=Expression("id").is_in(ids_to_delete))

# BAD - States the obvious
# Delete records with matching IDs
results = table.delete(ids=ids_to_delete)
```

---

## Git Workflow

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type       | Description                 |
| ---------- | --------------------------- |
| `feat`     | New feature                 |
| `fix`      | Bug fix                     |
| `docs`     | Documentation only          |
| `style`    | Formatting (no code change) |
| `refactor` | Code restructuring          |
| `perf`     | Performance improvement     |
| `test`     | Adding tests                |
| `chore`    | Maintenance                 |

### Example

```
feat(config): Add environment variable override support

Implement cascading config where environment variables take priority
over YAML settings. This enables container deployments.

- Add env_var_prefix setting
- Support PRJ_* environment variables
- Document override precedence

Closes #123
```

### Branch Naming

| Branch Type | Pattern     | Example                       |
| ----------- | ----------- | ----------------------------- |
| Feature     | `feature/*` | `feature/add-config-override` |
| Bugfix      | `bugfix/*`  | `bugfix/fix-url-validation`   |
| Hotfix      | `hotfix/*`  | `hotfix/security-patch`       |

---

## TL;DR Cheat Sheet

### Code Style

```python
# Type hints + async + docstrings
async def process_data(input_path: Path) -> dict:
    """Process data from file."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    # ...
```

### Naming

```python
# snake_case for functions/variables
def get_setting(key: str) -> Any: ...

# PascalCase for classes
class ConfigurationError(Exception): ...

# UPPER_SNAKE_CASE for constants
DEFAULT_TIMEOUT = 30
```

### Imports

```python
# Absolute for cross-package
from config.settings import get_setting

# Relative for same package
from .validation import validate

# No deep relative, no wildcard
```

### Testing

```python
# Parametrized tests
@pytest.mark.parametrize("input,expected", [
    ("valid", True),
    ("invalid", False),
])
def test_validate(input: str, expected: bool):
    assert validate(input) == expected
```

---

## Related Documents

- [Documentation Standards](./documentation-standards.md) - Documentation guidelines
- [MCP Best Practices](./mcp-best-practices.md) - MCP server development
- [Architecture Overview](../../docs/explanation/trinity-architecture.md) - Design decisions
