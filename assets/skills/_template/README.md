# Template Skill Guide

## Overview

Template skill demonstrating **Trinity Architecture v2.0** with **scripts/commands.py** pattern.

## Development Workflow

```
_template/                    # Start: Copy this template
   │
2. scripts/                   # Step 1: COMMANDS (actual implementation)
   ├── __init__.py            #    Dynamic module loader
   └── commands.py            #    @skill_command decorated functions
   │
3. tests/                     # Step 2: TESTS (zero-config pytest)
   └── test_template_commands.py
   │
4. references/                # Step 3: DOCUMENTATION
   └── skill-workflow.md
   │
5. README.md                  # Step 4: User documentation
   │
6. SKILL.md                   # Step 5: LLM context & manifest
```

---

## Step 1: COMMANDS (`scripts/commands.py`)

Commands are defined directly with `@skill_command` decorator:

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description",
    inject_root=True,  # Optional: inject project root
)
async def my_command(param: str = "default") -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

**No tools.py needed** - this is the single source of truth.

---

## Step 2: TESTS (`tests/`)

**Critical:** When adding commands, create corresponding tests.

### Test Structure

```
tests/
└── test_template_commands.py    # Test file for commands.py
```

### Test Pattern

```python
"""
tests/test_template_commands.py

Usage: uv run pytest assets/skills/_template/tests/ -v
"""
import pytest
import inspect
import sys
import types
import importlib.util
from pathlib import Path


def _setup_template_package_context():
    """Set up package hierarchy in sys.modules for template skill."""
    tests_dir = Path(__file__).parent
    template_dir = tests_dir.parent
    skills_root = template_dir.parent
    project_root = skills_root.parent.parent

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        sys.modules["agent.skills"] = skills_pkg

    # Ensure 'agent.skills._template' package exists
    template_pkg_name = "agent.skills._template"
    if template_pkg_name not in sys.modules:
        template_pkg = types.ModuleType(template_pkg_name)
        template_pkg.__path__ = [str(template_dir)]
        template_pkg.__file__ = str(template_dir / "__init__.py")
        sys.modules[template_pkg_name] = template_pkg

    # Ensure 'agent.skills._template.scripts' package exists
    scripts_pkg_name = "agent.skills._template.scripts"
    if scripts_pkg_name not in sys.modules:
        scripts_dir = template_dir / "scripts"
        scripts_pkg = types.ModuleType(scripts_pkg_name)
        scripts_pkg.__path__ = [str(scripts_dir)]
        scripts_pkg.__file__ = str(scripts_dir / "__init__.py")
        sys.modules[scripts_pkg_name] = scripts_pkg


_setup_template_package_context()


def test_example_exists():
    """Verify example command exists and is callable."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "example")
    assert callable(commands.example)


def test_example_with_options_exists():
    """Verify example_with_options command exists."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "example_with_options")
    assert callable(commands.example_with_options)


def test_process_data_exists():
    """Verify process_data command exists."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "process_data")
    assert callable(commands.process_data)
```

---

## Step 3: DOCUMENTATION (`references/`)

**Critical:** When adding new commands, create documentation.

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

## Step 4: User Docs (`README.md`)

Update with usage examples and command reference.

---

## Step 5: LLM Context (`SKILL.md`)

Update frontmatter and system prompts for LLM context.

---

## Complete Development Checklist

When adding a new command `my_command` in `scripts/commands.py`:

- [ ] **Command**: Add `@skill_command` decorated function in `scripts/commands.py`
- [ ] **Tests**: Add test in `tests/test_template_commands.py`
- [ ] **Docs**: Update `references/skill-workflow.md`
- [ ] **User Docs**: Update `README.md` with command reference
- [ ] **LLM Context**: Update `SKILL.md` if needed
- [ ] **Validate**: Run `just validate`

---

## Usage

### When to use

- Use `template.example` for basic operations
- Use `template.process_data` for data processing
- Define commands directly in `scripts/commands.py`

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

### Command Pattern (`scripts/commands.py`)

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description",
)
async def my_command(param: str = "default") -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

---

## Performance Notes

- **Import time:** Uses lazy initialization for fast loading
- **Execution:** O(1) command lookup via SkillManager cache
- **Hot reload:** Automatically reloads when `scripts/commands.py` is modified
- **Namespace isolation:** Each skill's scripts are in separate packages

---

## Creating a New Skill

```bash
# Copy template
cp -r assets/skills/_template assets/skills/my_skill

# Update SKILL.md frontmatter with new name/description

# Add commands in scripts/commands.py (with @skill_command decorator)
# Add tests in tests/ (required!)
# Add docs in references/ (required!)
```

---

## Testing

Skills use **zero-configuration testing** via the Pytest plugin.

### Running Tests

```bash
# Run skill-specific tests
uv run pytest assets/skills/_template/tests/ -v

# Run all skill tests
uv run pytest assets/skills/ -v

# Run via omni CLI (if testing_protocol loaded)
omni skill test template

# Run all skills
omni skill test --all
```

### Best Practices

1. **Test existence first**: `test_*_exists()` for each command
2. **Test callability**: Verify functions are callable
3. **Use package context:** Set up sys.modules for imports
4. **SSOT paths:** Use relative path computation from `__file__`
5. **Always test:** When commands are modified, tests MUST be updated

### Example Test Output

```
$ uv run pytest assets/skills/_template/tests/ -v

assets/skills/_template/tests/test_template_commands.py::test_example_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_example_with_options_exists PASSED
assets/skills/_template/tests/test_template_commands.py::test_process_data_exists PASSED
============================== 3 passed in 0.05s ===============================
```

---

## Related

- [SKILL.md](./SKILL.md) - Full skill manifest
- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
