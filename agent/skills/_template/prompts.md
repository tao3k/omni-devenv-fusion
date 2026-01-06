# Template Skill Prompts

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

- Consider using the template skill tools for [specific tasks]
- Remember to [relevant considerations]

## Creating a New Skill

Use `_template` as a scaffold for new skills:

1. Copy `_template/` directory to new skill name
2. Update `manifest.json` with skill metadata
3. Add `@skill_command` decorated functions in `tools.py`:

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_skill_my_command",
    category="read",
    description="Brief description",
)
async def my_command(param: str) -> str:
    """Detailed docstring."""
    return "result"
```

4. Update `prompts.md` with skill-specific guidelines
