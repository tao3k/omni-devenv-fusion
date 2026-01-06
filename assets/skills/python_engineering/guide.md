# Python Engineering Skill Guide

This skill provides Python development utilities including linting, testing, and adherence to Pydantic patterns.

## When to Use This Skill

Use this skill when:

- Writing new Python code
- Running tests (pytest)
- Linting and formatting code
- Working with Pydantic models
- Type checking with pyright/mypy

## Python Standards

### PEP 8 Style Guide

- Use 4 spaces for indentation
- Limit lines to 88 characters (Black default)
- Use descriptive variable names
- Write docstrings for public functions and classes

### Pydantic Patterns

- Use `BaseModel` for data structures
- Define types using Python type hints
- Use `Field` for validation and description
- Prefer `model_validator` over `root_validator`

### Type Hints

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str
    email: str
    age: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
```

## Testing with Pytest

- Place tests in `tests/` directory
- Use `test_` prefix for test functions
- Use `pytest.ini` or `pyproject.toml` for configuration
- Run with `pytest` command
