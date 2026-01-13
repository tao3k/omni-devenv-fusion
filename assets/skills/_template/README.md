# Template Skill Guide

## Overview

Template skill demonstrating **Trinity Architecture** with **Router-Controller** pattern.

## Development Workflow

```
1. _template/                    # Start: Copy this template
   │
2. tools.py                     # Step 1: ROUTER (just dispatches)
   │
3. scripts/                     # Step 2: CONTROLLER (actual logic)
   ├── __init__.py
   ├── command.py               # Command implementations
   └── rendering.py             # Template rendering (optional)
   │
4. tests/                       # Step 3: TESTS (zero-config pytest)
   └── test_commands.py
   │
5. references/                  # Step 4: DOCUMENTATION
   └── skill-workflow.md        # Command documentation
   │
6. README.md                    # Step 5: User documentation
   │
7. SKILL.md                     # Step 6: LLM context & manifest
```

---

## Step 1: ROUTER (`tools.py`)

Lightweight dispatcher - only imports from scripts:

```python
from agent.skills.decorators import skill_command

@skill_command(name="example", category="read", description="Brief desc")
def example(param: str = "default") -> str:
    """Detailed docstring."""
    from agent.skills._template.scripts import example as mod
    return mod.example_command(param)
```

---

## Step 2: CONTROLLER (`scripts/`)

Actual implementation - fully isolated namespace:

```python
# scripts/example.py
def example_command(param: str = "default") -> str:
    """Actual implementation."""
    return f"Result: {param}"
```

---

## Step 3: TESTS (`tests/`)

**Critical:** When adding or modifying scripts/ files, you MUST create corresponding tests.

### Test Naming Convention

```
tests/
├── test_commands.py           # Command existence & metadata tests
└── test_example.py            # Test for scripts/example.py
```

### Test Pattern

```python
"""
tests/test_example.py

Auto-generated when scripts/example.py is created.
"""
import pytest
import inspect

from common.skills_path import SKILLS_DIR


def test_example_command_exists(my_skill):
    """Verify example command exists and is callable."""
    assert hasattr(my_skill, "example")
    assert callable(my_skill.example)


def test_example_command_execution(my_skill):
    """Test example command execution."""
    result = my_skill.example(param="test")
    assert "test" in result if hasattr(result, "data") else isinstance(result, str)
```

---

## Step 4: DOCUMENTATION (`references/`)

**Critical:** When adding new commands, you MUST create documentation.

### Documentation Structure

```
references/
└── skill-workflow.md          # Command documentation (required)
```

### Documentation Template (`references/skill-workflow.md`)

````markdown
# Example Skill Workflow

## Commands

### `example`

**Description:** Brief description of the command.

**Usage:**

```python
@omni("template.example", {"param": "value"})
```
````

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param` | string | No | "default" | Description |

**Returns:** String result.

````

---

## Step 5: User Docs (`README.md`)

Update with usage examples and command reference.

---

## Step 6: LLM Context (`SKILL.md`)

Update frontmatter and system prompts for LLM context.

---

## Complete Development Checklist

When adding a new command `my_command` in `scripts/my_command.py`:

- [ ] **Router**: Add `tools.my_command()` decorator in `tools.py`
- [ ] **Controller**: Implement `scripts/my_command.py`
- [ ] **Tests**: Create `tests/test_my_command.py`
- [ ] **Docs**: Create `references/skill-workflow.md` or update existing
- [ ] **User Docs**: Update `README.md` with command reference
- [ ] **LLM Context**: Update `SKILL.md` if needed
- [ ] **Validate**: Run `just validate`

---

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
````

---

## Commands Reference

| Command                         | Category | Description                      |
| ------------------------------- | -------- | -------------------------------- |
| `template.example`              | read     | Example command with parameter   |
| `template.example_with_options` | read     | Example with optional parameters |
| `template.process_data`         | write    | Process a list of data strings   |
| `template.help`                 | view     | Show full skill context          |

---

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

---

## Performance Notes

- **Import time:** Uses lazy initialization for fast loading
- **Execution:** O(1) command lookup via SkillManager cache
- **Hot reload:** Automatically reloads when `tools.py` or `scripts/*.py` is modified
- **Namespace isolation:** Each skill's scripts are in separate packages

---

## Creating a New Skill

```bash
# Copy template
cp -r assets/skills/_template assets/skills/my_skill

# Update SKILL.md frontmatter with new name/description

# Add commands in tools.py (router)
# Add implementations in scripts/ (controllers)
# Add tests in tests/ (required!)
# Add docs in references/ (required!)
```

---

## Testing (Phase 35.1)

Skills use **zero-configuration testing** via the Pytest plugin.

### Test Structure

```
my_skill/
├── tests/                    # Required: Skill-specific tests
│   ├── test_commands.py     # Test file pattern: test_*.py
│   └── test_my_command.py   # Tests for scripts/my_command.py
└── tools.py                 # Your skill commands
```

### Writing Tests

```python
"""
tests/test_my_command.py

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
6. **Always test**: When scripts/ is modified, tests/ MUST be updated

### Example Test Output

```
$ uv run pytest assets/skills/_template/tests/ -v

assets/skills/_template/tests/test_template_commands.py::test_example_command_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_process_data_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_commands_have_metadata PASSED
============================== 3 passed in 0.05s ===============================
```

---

## Related

- [SKILL.md](./SKILL.md) - Full skill manifest
- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
