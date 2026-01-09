# Template Skill Guide

## Overview

Template skill demonstrating **Trinity Architecture** with **Isolated Sandbox + Explicit Routing** pattern.

## Architecture (Phase 35.2)

```
_template/
├── SKILL.md           # Metadata + System Prompts
├── tools.py           # Router (dispatch only)
└── scripts/           # Controllers (isolated implementation)
    ├── __init__.py    # Package marker (required!)
    └── example.py     # Atomic implementations
```

| Component   | File                    | Purpose                       |
| ----------- | ----------------------- | ----------------------------- |
| **Code**    | `tools.py` + `scripts/` | Hot-reloaded via ModuleLoader |
| **Context** | `SKILL.md`              | LLM behavior guidelines       |
| **State**   | `SKILL.md` Frontmatter  | Metadata and configuration    |

## Why Isolated Sandbox?

For 100+ skills, namespace conflicts are inevitable:

```text
git/scripts/status.py      ← Git's status
docker/scripts/status.py   ← Docker's status
```

Each `scripts/` is a **separate Python package**:

- `agent.skills.git.scripts.status` ≠ `agent.skills.docker.scripts.status`

## Usage

### When to use

- Use `template.example` for basic operations
- Use `template.process_data` for data processing
- Follow the Router-Controller pattern for new commands

### Examples

```bash
# Run a command
@omni("template.example", {"param": "value"})

# Get skill context
@omni("template.help")

# List available commands
@omni("template")
```

## Commands

| Command                         | Category | Description                      |
| ------------------------------- | -------- | -------------------------------- |
| `template.example`              | read     | Example command with parameter   |
| `template.example_with_options` | read     | Example with optional parameters |
| `template.process_data`         | write    | Process a list of data strings   |
| `template.help`                 | view     | Show full skill context          |

## Command Details

### `example`

**Description:** Example command with parameter.

**Usage:**

```bash
@omni("template.example", {"param": "test_value"})
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param` | string | No | "default" | Description of the parameter |

**Examples:**

```bash
@omni("template.example", {"param": "my_value"})
```

### `process_data`

**Description:** Process a list of data strings with optional filtering.

**Usage:**

```bash
@omni("template.process_data", {"data": ["a", "", "b"], "filter_empty": true})
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `data` | array | Yes | - | Input data strings |
| `filter_empty` | boolean | No | true | Whether to remove empty strings |

**Returns:**

```json
{
  "processed": ["a", "b"],
  "count": 2,
  "original_count": 3
}
```

## ODF-EP Compliance

This skill template follows the **"Python Zenith" Engineering Protocol**:

### Router Pattern (`tools.py`)

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="example",
    category="read",
    description="Brief description",
)
def example(param: str = "default") -> str:
    """Detailed docstring."""
    from agent.skills._template.scripts import example as example_mod
    return example_mod.example_command(param)
```

### Controller Pattern (`scripts/example.py`)

```python
def example_command(param: str = "default") -> str:
    """Actual implementation."""
    return f"Result: {param}"
```

## Performance Notes

- **Import time:** Uses lazy initialization for fast loading
- **Execution:** O(1) command lookup via SkillManager cache
- **Hot reload:** Automatically reloads when `tools.py` or `scripts/*.py` is modified
- **Namespace isolation:** Each skill's scripts are in separate packages

## Creating a New Skill

```bash
# Copy template
cp -r assets/skills/_template assets/skills/my_skill

# Update SKILL.md frontmatter with new name/description

# Add commands in tools.py (router)
# Add implementations in scripts/ (controllers)
```

## Testing (Phase 35.1)

Skills use **zero-configuration testing** via the Pytest plugin.

### Test Structure

```
my_skill/
├── tests/                    # Optional: Skill-specific tests
│   └── test_commands.py     # Test file pattern: test_*.py
└── tools.py                 # Your skill commands
```

### Writing Tests

```python
"""
my_skill/tests/test_commands.py

Usage:
    def test_my_command(my_skill):  # 'my_skill' fixture auto-injected
        assert hasattr(my_skill, "my_command")
"""

import pytest
import inspect

# SSOT: Use common.skills_path for path resolution
from common.skills_path import SKILLS_DIR


def test_my_command_exists(my_skill):
    """Verify my_command exists and is callable."""
    assert hasattr(my_skill, "my_command")
    assert callable(my_skill.my_command)


def test_commands_have_metadata(my_skill):
    """All commands should have @skill_command metadata."""
    for name, func in inspect.getmembers(my_skill, inspect.isfunction):
        if hasattr(func, "_is_skill_command"):
            assert hasattr(func, "_skill_config")
            config = func._skill_config
            assert "name" in config
            assert "category" in config


def test_my_command_execution(my_skill):
    """Test command execution."""
    result = my_skill.my_command(param="value")

    # Handle CommandResult wrapper
    if hasattr(result, "data"):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
```

### Available Fixtures

| Fixture        | Description                                  |
| -------------- | -------------------------------------------- |
| `my_skill`     | The skill module (tools.py loaded as module) |
| `project_root` | Project root directory (git toplevel)        |
| `skills_root`  | Skills directory (assets/skills)             |
| `temp_dir`     | Temporary directory for tests                |

### Running Tests

```bash
# Run skill-specific tests
uv run pytest assets/skills/my_skill/tests/ -v

# Run all skill tests
uv run pytest assets/skills/ -v

# Run via omni CLI (if testing_protocol loaded)
omni skill test my_skill

# Run all skills
omni skill test --all
```

### Best Practices

1. **Test existence first**: `test_*_exists()` for each command
2. **Test metadata**: Verify `@skill_command` decorators are present
3. **Test execution**: Use CommandResult wrapper pattern
4. **Use fixtures**: Leverage auto-injected `project_root`, `temp_dir`
5. **SSOT paths**: Use `SKILLS_DIR()` for path resolution

### Example Test Output

```
$ uv run pytest assets/skills/_template/tests/ -v

assets/skills/_template/tests/test_template_commands.py::test_example_command_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_process_data_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_commands_have_metadata PASSED
============================== 3 passed in 0.05s ===============================
```

## Related

- [SKILL.md](./SKILL.md) - Full skill manifest
- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
