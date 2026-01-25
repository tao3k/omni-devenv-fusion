---
name: "python_engineering"
version: "1.1.0"
description: "Python development utilities including linting, testing, and Pydantic standards. Supports Python 3.12+ modernization."
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
    "modernize",
    "upgrade",
    "refactor 3.12",
    "match case",
    "override",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Python linting and formatting"
  - "Check Python imports"
  - "Python type checking"
  - "Pytest testing"
  - "Modernize Python code to 3.12+ standards"
---

# Python Engineering Skill Policy

> **Code is Mechanism, Prompt is Policy**

## Python Standards (v2.0 - Modern)

When writing or editing Python code:

1. **State Management** - Use `StrEnum` instead of magic strings
2. **Control Flow** - Prefer `match/case` over complex `if/elif` chains
3. **Type Safety** - Use `@override` for inherited methods and new generic syntax `class Foo[T]`
4. **Concurrency** - Use `asyncio.TaskGroup` instead of `gather`
5. **Legacy Standards** - Follow PEP 8, 4 spaces, and Google style docstrings

See [lang-python-modern.md](../knowledge/references/standards/lang-python-modern.md) for complete standards.

## Tools Available

- `lint_python_style` - Check code with ruff/flake8 (Configured for py313)
- `run_pytest` - Execute test suite
- `check_types` - Run pyright type checking
- `format_python` - Format code with ruff/black

## Routing Keywords

Python, lint, format, type check, pytest, pep8, pydantic, type hints, typing, ruff, black, modernize, upgrade, refactor 3.12, match case, override
