# Template Skill Guide

## Overview

Brief description of what this skill does and its primary use cases.

## Trinity Architecture

This skill operates within the **Trinity Architecture**:

| Component   | File         | Purpose                       |
| ----------- | ------------ | ----------------------------- |
| **Code**    | `tools.py`   | Hot-reloaded via ModuleLoader |
| **Context** | `prompts.md` | LLM behavior guidelines       |
| **State**   | `SKILL.md`   | Metadata and configuration    |

## Usage

### When to use

- Scenario 1 where this skill excels
- Scenario 2 for complex workflows
- Scenario 3 for automation

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

| Command   | Category | Description                                 |
| --------- | -------- | ------------------------------------------- |
| `example` | read     | Brief description of what this command does |

## Command Details

### `example`

**Description:** Brief description of what this command does.

**Usage:**

```bash
@omni("template.example", {"param": "value"})
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `param` | string | Yes | Description of the parameter |

**Examples:**

```bash
@omni("template.example", {"param": "test_value"})
```

## ODF-EP Compliance

This skill template follows the **"Python Zenith" Engineering Protocol**:

```python
# tools.py - @skill_command decorator pattern
from agent.skills.decorators import skill_command

@skill_command(
    name="example",
    category="read",
    description="Brief description",
)
async def example(param: str) -> str:
    """Detailed docstring explaining the command."""
    return "result"
```

## Performance Notes

- **Import time:** Uses lazy initialization for fast loading
- **Execution:** O(1) command lookup via SkillManager cache
- **Hot reload:** Automatically reloads when `tools.py` is modified

## Related

- [Template Prompts](./prompts.md) - LLM context
- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [ODF-EP Planning Prompt](../../.claude/plans/odf-ep-v6-planning-prompt.md)
