# Test Skill Guide

## Overview

Test skill demonstrating **Trinity Architecture v2.0** with **scripts/commands.py** pattern (Phase 63+).

## Architecture (Phase 63+)

```
test-skill/
├── SKILL.md           # Metadata + System Prompts
└── scripts/           # @skill_script decorated commands
    ├── __init__.py    # Package marker (required!)
    └── test.py        # Command implementations
```

| Component   | File                   | Purpose                       |
| ----------- | ---------------------- | ----------------------------- |
| **Code**    | `scripts/`             | Hot-reloaded via ModuleLoader |
| **Context** | `SKILL.md`             | LLM behavior guidelines       |
| **State**   | `SKILL.md` Frontmatter | Metadata and configuration    |

## Usage

### When to use

- Use `test-skill.example` for basic operations
- Use `test-skill.process_data` for data processing
- Commands are defined directly in `scripts/test.py` with @skill_script

### Examples

```bash
# Run a command
@omni("test-skill.example", {"param": "value"})

# Get skill context
@omni("test-skill.help")

# List available commands
@omni("test-skill")
```

## Commands

| Command                           | Category | Description                      |
| --------------------------------- | -------- | -------------------------------- |
| `test-skill.example`              | read     | Example command with parameter   |
| `test-skill.example_with_options` | read     | Example with optional parameters |
| `test-skill.process_data`         | write    | Process a list of data strings   |
| `test-skill.help`                 | view     | Show full skill context          |

## @skill_script Pattern

Commands in `scripts/test.py` are decorated with `@skill_script`:

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="example",
    category="read",
    description="Brief description",
)
async def example(param: str = "default") -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

## Performance Notes

- **Import time:** Uses lazy initialization for fast loading
- **Execution:** O(1) command lookup via SkillManager cache
- **Hot reload:** Automatically reloads when `scripts/test.py` is modified
- **Namespace isolation:** Each skill's scripts are in separate packages

## Testing

Skills use **zero-configuration testing** via the Pytest plugin.

### Running Tests

```bash
# Run skill-specific tests
uv run pytest assets/skills/test-skill/tests/ -v

# Run all skill tests
uv run pytest assets/skills/ -v
```

## Related

- [SKILL.md](./SKILL.md) - Full skill manifest
- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
