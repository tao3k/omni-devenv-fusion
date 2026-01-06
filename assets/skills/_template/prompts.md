# Template Skill Prompts

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

- Consider using the template skill tools for [specific tasks]
- Remember to [relevant considerations]

## Trinity Architecture Context

This skill operates within Phase 25.3 Trinity Architecture:

- **Code**: Tools are hot-reloaded automatically when `tools.py` is modified
- **Context**: Use `@omni("template.help")` to get full skill context (XML via Repomix)
- **State**: Skill registry maintains metadata and command definitions

## Creating a New Skill

Use `_template` as a scaffold for new skills:

1. Copy `_template/` directory to new skill name
2. Add `@skill_command` decorated functions in `tools.py`:

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description",
)
async def my_command(param: str) -> str:
    """Detailed docstring."""
    return "result"
```

3. (Optional) Add `repomix.json` for atomic context:

```json
{
  "output": { "style": "xml", "fileSummary": true },
  "include": ["tools.py", "prompts.md", "guide.md"],
  "ignore": { "patterns": [], "characters": [] }
}
```

4. Update `prompts.md` with skill-specific guidelines
