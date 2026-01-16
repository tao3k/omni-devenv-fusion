---
# === Omni-Dev Fusion Skill Manifest ===
name: test-skill
version: 1.0.0
description: Test skill for verifying skill system functionality - demonstrates @skill_script pattern
authors: ["omni-dev-fusion"]
license: Apache-2.0
execution_mode: library
routing_strategy: keyword
routing_keywords: ["test", "verify", "demo", "example"]
intents: []
---

# Test Skill

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

```markdown
# Test Skill Guidelines

When working with the Test skill:

- Use `test-skill.example` for basic test operations
- Use `test-skill.example_with_options` for testing optional parameters
- Use `test-skill.process_data` for data processing tests
- All commands use @skill_script decorator - no tools.py needed
```

## Trinity Architecture Context (Phase 63+)

This skill operates within the **Trinity Architecture v2.0** with **scripts/commands.py** pattern:

```
test-skill/
├── SKILL.md           # Metadata + System Prompts
└── scripts/           # Commands (@skill_script decorated)
    ├── __init__.py    # Package marker (required!)
    ├── test.py        # @skill_script commands
    └── ...
```

| Component   | Description                                                     |
| ----------- | --------------------------------------------------------------- |
| **Code**    | `scripts/` - Hot-reloaded via ModuleLoader                      |
| **Context** | `@omni("test-skill.help")` - Full skill context via Repomix XML |
| **State**   | `SKILL.md` - Skill metadata in YAML Frontmatter                 |

## Creating a New Skill

Use `_template` as a scaffold for new skills:

### 1. Copy Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Update SKILL.md

Edit the frontmatter:

```yaml
---
name: my_new_skill
version: 1.0.0
description: My new skill description
routing_keywords: ["keyword1", "keyword2"]
---
```

### 3. Add Commands (`scripts/commands.py`)

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="my_command",
    category="read",
    description="Brief description",
)
async def my_command(param: str) -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

**Note:** Command name is just `my_command`, not `my_new_skill.my_command`. MCP Server auto-prefixes.

### 4. (Optional) Add Jinja2 Templates

For structured output:

```bash
mkdir -p assets/templates/my_new_skill/
# Add *.j2 template files
```

## Quick Reference

| Command                           | Category | Description             |
| --------------------------------- | -------- | ----------------------- |
| `test-skill.example`              | read     | Example command         |
| `test-skill.example_with_options` | read     | Example with options    |
| `test-skill.process_data`         | write    | Process data strings    |
| `test-skill.help`                 | view     | Show full skill context |

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
