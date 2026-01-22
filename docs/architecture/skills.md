# Skills System - Omni-Dev-Fusion

> Zero-Code Skill Architecture for Omni-Dev-Fusion
> Last Updated: 2026-01-20

---

## Table of Contents

1. [Overview](#overview)
2. [Zero-Code Skill Architecture](#zero-code-skill-architecture)
3. [Skill Directory Structure](#skill-directory-structure)
4. [Skill List](#skill-list)
5. [Skill Metadata](#skill-metadata)
6. [Commands](#commands)
7. [Extensions](#extensions)
8. [Tests](#tests)
9. [Creating New Skills](#creating-new-skills)

---

## Overview

The Skills System provides a declarative, Zero-Code approach to defining AI tools. Each skill is a self-contained unit with:

- **Documentation**: `SKILL.md` with YAML frontmatter metadata
- **Commands**: Python scripts with `@skill_command` decorators
- **Extensions**: Optional Rust extensions for performance
- **Tests**: Skill-specific test suite

### Design Principles

1. **Declarative**: Skills are defined by metadata, not code
2. **Self-Contained**: Each skill has its own directory with everything it needs
3. **Extensible**: Optional Rust extensions for performance-critical operations
4. **Testable**: Built-in test framework for each skill

---

## Zero-Code Skill Architecture

### Concept

Skills follow the Zero-Code pattern where most functionality is defined declaratively:

```yaml
---
# assets/skills/git/SKILL.md
name: git
description: Git operations skill
version: 1.0.0
author: Omni Team
commands:
  - name: status
    description: Show working tree status
    parameters:
      type: object
      properties:
        short:
          type: boolean
          description: Show short format
  - name: commit
    description: Commit changes to repository
    parameters:
      type: object
      properties:
        message:
          type: string
          description: Commit message
        amend:
          type: boolean
          description: Amend to previous commit
---
```

### Execution Flow

```
User Request (@omni("git.commit"))
        │
        ▼
┌───────────────────┐
│  OmniRouter       │  # Route to git skill
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  SkillDiscovery   │  # Find git skill
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  ScriptLoader     │  # Load commands.py
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  skill_command    │  # Execute decorated function
│  decorator        │
└───────────────────┘
```

---

## Skill Directory Structure

### Standard Skill Layout

```
assets/skills/{skill_name}/
├── SKILL.md                   # Skill documentation + YAML frontmatter
├── README.md                  # Additional readme (optional)
├── pyproject.toml             # Skill-specific dependencies (optional)
├── scripts/
│   ├── __init__.py
│   ├── commands.py            # Command implementations
│   └── ...                    # Additional script modules
├── extensions/                # Optional Rust extensions
│   ├── Cargo.toml
│   ├── src/
│   │   └── lib.rs
│   └── tests/
│       └── test_extension.rs
├── references/                # Reference documentation
│   └── ...
├── tests/                     # Skill-specific tests
│   ├── __init__.py
│   ├── test_commands.py
│   └── test_data/
│       └── ...
└── assets/                    # Skill-specific assets
    └── ...
```

### Minimal Skill Layout

```
assets/skills/minimal/
├── SKILL.md
└── scripts/
    ├── __init__.py
    └── commands.py
```

---

## Skill List

### Development Skills

| Skill                  | Description                  | Commands                    |
| ---------------------- | ---------------------------- | --------------------------- |
| `code_tools`           | Code analysis and navigation | analyze, navigate, refactor |
| `software_engineering` | General software engineering | build, test, lint           |
| `python_engineering`   | Python-specific tools        | py.test, py.lint, py.format |
| `rust_engineering`     | Rust-specific tools          | cargo.test, cargo.build     |
| `terminal`             | Terminal commands            | exec, shell                 |
| `testing`              | Testing tools                | pytest, coverage            |
| `testing_protocol`     | Testing protocol management  | protocol.test               |

### Git Operations

| Skill | Description    | Commands                                     |
| ----- | -------------- | -------------------------------------------- |
| `git` | Git operations | status, commit, branch, checkout, push, pull |

### Knowledge Skills

| Skill           | Description                         | Commands             |
| --------------- | ----------------------------------- | -------------------- |
| `knowledge`     | Knowledge base management           | search, add, update  |
| `memory`        | Memory/session management           | save, recall, forget |
| `note_taker`    | Note taking & session summarization | note, summarize      |
| `documentation` | Documentation generation            | doc.generate         |
| `crawl4ai`      | Web crawling                        | crawl, scrape        |

### Meta Skills

| Skill   | Description      | Commands                     |
| ------- | ---------------- | ---------------------------- |
| `skill` | Skill management | discover, load, reload, list |
| `meta`  | Meta-operations  | refine, analyze              |

### Utility Skills

| Skill            | Description              | Commands                  |
| ---------------- | ------------------------ | ------------------------- |
| `filesystem`     | File operations          | read, write, list, delete |
| `writer`         | Writing/text tools       | write, edit, format       |
| `advanced_tools` | Advanced tool operations | grep, find, replace       |

### Skill Template

| Skill       | Description                      |
| ----------- | -------------------------------- |
| `_template` | Template for creating new skills |

---

## Skill Metadata

### SKILL.md Frontmatter

````yaml
---
name: skill_name
description: One-line description of the skill
version: 1.0.0
author: Author Name
tags: [tag1, tag2, tag3]
commands:
  - name: command1
    description: Description of command1
    parameters:
      type: object
      properties:
        param1:
          type: string
          description: Description of param1
      required: [param1]
  - name: command2
    description: Description of command2
---

# Skill Documentation

Detailed documentation about this skill...

## Usage

```python
@omni("skill_name.command1", param1="value")
````

## Examples

Example usage of this skill...

````

### Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Skill name (kebab-case) |
| `description` | string | Yes | One-line description |
| `version` | string | No | Semantic version (default: 1.0.0) |
| `author` | string | No | Author name |
| `tags` | array | No | Tags for categorization |
| `commands` | array | Yes | List of commands |

### Commands Array

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Command name (snake_case) |
| `description` | string | Yes | Command description |
| `parameters` | object | No | JSON Schema for parameters |

---

## Commands

### Command Implementation

Commands are implemented in `scripts/commands.py` using the `@skill_command` decorator:

```python
"""Commands for git skill."""

from typing import Annotated
from omni.core.skills.script_loader import skill_command


@skill_command
def status(short: Annotated[bool, "Show short format"] = False) -> dict:
    """Show working tree status."""
    import subprocess

    if short:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True
        )
    else:
        result = subprocess.run(
            ["git", "status"],
            capture_output=True,
            text=True
        )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }


@skill_command
def commit(
    message: Annotated[str, "Commit message"],
    amend: Annotated[bool, "Amend to previous commit"] = False
) -> dict:
    """Commit changes to repository."""
    import subprocess

    args = ["git", "commit"]
    if amend:
        args.append("--amend")
    args.extend(["-m", message])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }
````

### Parameter Types

| Type    | Python Type | YAML Schema Type |
| ------- | ----------- | ---------------- |
| String  | `str`       | `string`         |
| Integer | `int`       | `integer`        |
| Float   | `float`     | `number`         |
| Boolean | `bool`      | `boolean`        |
| Array   | `list`      | `array`          |
| Object  | `dict`      | `object`         |

### Decorator Options

```python
@skill_command(
    name="custom_name",  # Override command name
    description="Custom description"  # Override description
)
def my_command():
    pass
```

---

## Extensions

### Purpose

Extensions provide Rust implementations for performance-critical operations:

```python
"""Git skill with Rust accelerator."""

from omni.core.skills.extensions import SkillExtension


class GitRustExtension(SkillExtension):
    """Rust accelerator for git operations."""

    def __init__(self):
        # Load Rust library
        from omni.foundation.bridge import rust_impl
        self._lib = rust_impl.load_library("omni_git")

    async def fast_status(self, path: str) -> dict:
        """Fast status using Rust."""
        return self._lib.git_status(path.encode())

    async def fast_commit(self, path: str, message: str) -> dict:
        """Fast commit using Rust."""
        return self._lib.git_commit(path.encode(), message.encode())
```

### Extension Structure

```
assets/skills/git/extensions/
├── Cargo.toml
├── src/
│   └── lib.rs
│
├── tests/
│   └── test_extension.rs
│
├── rust_bridge/              # Common Rust bridge pattern
│   ├── __init__.py
│   ├── bindings.py
│   └── accelerator.py
│
└── sniffer/                  # Sniffer extensions
    ├── __init__.py
    ├── loader.py
    └── decorators.py
```

---

## Tests

### Test Structure

```
assets/skills/{skill_name}/tests/
├── __init__.py
├── test_commands.py
├── test_data/
│   ├── sample_file.py
│   └── sample_file.rs
└── fixtures/
    └── ...
```

### Example Test

```python
"""Tests for git skill."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestGitStatus:
    """Tests for git status command."""

    def test_status_returns_result(self, git):
        """Test that status command returns expected structure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="On branch main\n",
                stderr=""
            )

            result = git.status()

            assert result["success"] is True
            assert "main" in result["output"]

    def test_status_short_format(self, git):
        """Test short format status."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=" M file.py\n",
                stderr=""
            )

            result = git.status(short=True)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "--short" in args
```

### Running Skill Tests

```bash
# Run all skill tests
uv run pytest assets/skills/*/tests/ -v

# Run specific skill tests
uv run pytest assets/skills/git/tests/ -v

# Run single test file
uv run pytest assets/skills/git/tests/test_commands.py::TestGitStatus::test_status_returns_result -v
```

---

## Creating New Skills

### Using the Template

1. Copy the template:

   ```bash
   cp -r assets/skills/_template assets/skills/my_new_skill
   ```

2. Update `SKILL.md`:

   ```yaml
   ---
   name: my_new_skill
   description: Description of my new skill
   commands:
     - name: hello
       description: Say hello
   ---
   ```

3. Implement commands in `scripts/commands.py`:

   ```python
   @skill_command
   def hello(name: str = "World") -> str:
       """Say hello to someone."""
       return f"Hello, {name}!"
   ```

4. Test the skill:

   ```bash
   uv run pytest assets/skills/my_new_skill/tests/ -v
   ```

5. Reload skills:
   ```bash
   @omni("skill.reload")
   ```

### Best Practices

1. **Naming**: Use kebab-case for skill names (`my-new-skill`)
2. **Commands**: Use snake_case for command names (`my_command`)
3. **Documentation**: Write clear descriptions for each command
4. **Parameters**: Provide default values when possible
5. **Error Handling**: Return structured error responses
6. **Tests**: Write tests for each command

---

## Skill Index

The skill index is automatically generated and stored in `assets/skill_index.json`:

```json
{
  "skills": [
    {
      "name": "git",
      "description": "Git operations skill",
      "commands": ["status", "commit", "branch", "checkout", "push", "pull"],
      "path": "assets/skills/git",
      "version": "1.0.0"
    }
  ],
  "commands": [
    {
      "skill": "git",
      "name": "status",
      "description": "Show working tree status"
    }
  ]
}
```

---

## Related Documentation

- [Codebase Structure](codebase-structure.md)
- [Rust Crates](rust-crates.md)
- [Zero-Code Skill Architecture](../explanation/zero-code-skill-architecture.md)
- [Skills Documentation](../skills.md)
