---
name: "python_engineering"
version: "1.0.0"
description: "Python development utilities including linting, testing, and Pydantic standards"
routing_keywords:
  [
    "python",
    "lint",
    "format",
    "type check",
    "pytest",
    "pep8",
    "pydantic",
    "type hints",
    "typing",
    "ruff",
    "black",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Python linting and formatting"
  - "Check Python imports"
  - "Python type checking"
  - "Pytest testing"
---

# Python Engineering Skill Policy

> **Code is Mechanism, Prompt is Policy**

## Python Standards

When writing or editing Python code:

1. **Follow PEP 8** - Use 4 spaces, 79-char line limit, descriptive names
2. **Use type hints** - All functions should have type annotations
3. **Pydantic patterns** - Use pydantic.BaseModel for data classes
4. **Docstrings** - Use Google style for function docstrings

## Tools Available

- `lint_python_style` - Check code with ruff/flake8
- `run_pytest` - Execute test suite
- `check_types` - Run mypy type checking
- `format_python` - Format code with ruff/black

## Routing Keywords

Python, lint, format, type check, pytest, pep8, pydantic, type hints, typing, ruff, black
