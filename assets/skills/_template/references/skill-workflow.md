---
for_skill: _template
title: Template Skill Workflow
---

# Template Skill Workflow

## Overview

This document describes the workflow and commands for the Template skill.

## Commands

### `example`

**Description:** Example command with parameter.

**Usage:**

```python
@omni("template.example", {"param": "test_value"})
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param` | string | No | "default" | Description of the parameter |

**Returns:** String result with the parameter value.

**Example:**

```python
@omni("template.example", {"param": "hello"})
# Returns: "Result: hello"
```

---

### `example_with_options`

**Description:** Example command with optional parameters.

**Usage:**

```python
@omni("template.example_with_options", {"param": "value", "optional": "opt"})
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param` | string | Yes | - | Main parameter |
| `optional` | string | No | "default" | Optional parameter |

**Returns:** Formatted string with both parameters.

---

### `process_data`

**Description:** Process a list of data strings with optional filtering.

**Usage:**

```python
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

---

### `help`

**Description:** Show full skill context and help information.

**Usage:**

```python
@omni("template.help")
```

**Returns:** Formatted help text with all commands and descriptions.

---

## Implementation Details

### @skill_command Pattern

Commands in `scripts/commands.py` are decorated with `@skill_command`:

```python
from agent.skills.decorators import skill_command

@skill_command(name="example", category="read", description="Brief desc")
async def example(param: str = "default") -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

All logic is in the same file - no router/controller separation needed.

---

## Related

- [README.md](../README.md) - Full skill guide
- [SKILL.md](../SKILL.md) - LLM context manifest
