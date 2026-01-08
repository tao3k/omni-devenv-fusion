---
# === Omni-Dev Fusion Skill Manifest ===
name: _template
version: 1.0.0
description: Template skill for new capabilities
authors: ["omni-dev-fusion"]
license: Apache-2.0
execution_mode: library
routing_strategy: keyword
routing_keywords: ["template", "new skill", "create skill", "scaffold"]
intents: []
---

# Template Skill

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

```markdown
# Template Skill Guidelines

When working with the Template skill:

- Consider using `template.example` for [specific tasks]
- Remember to [relevant considerations]
- Follow the skill's defined workflow for best results
```

## Trinity Architecture Context

This skill operates within the **Trinity Architecture**:

| Component   | Description                                                      |
| ----------- | ---------------------------------------------------------------- |
| **Code**    | `tools.py` - Hot-reloaded via ModuleLoader on `tools.py` changes |
| **Context** | `@omni("template.help")` - Full skill context via Repomix XML    |
| **State**   | `SKILL.md` - Skill metadata in YAML Frontmatter                  |

## ODF-EP Protocol Awareness

All core skill modules follow the **"Python Zenith" Engineering Protocol**:

| Pillar                             | Implementation in Skills              |
| ---------------------------------- | ------------------------------------- |
| **A: Pydantic Shield**             | DTOs use `ConfigDict(frozen=True)`    |
| **B: Protocol-Oriented Design**    | `ISkill`, `ISkillCommand` protocols   |
| **C: Tenacity Pattern**            | `@retry` for resilient I/O operations |
| **D: Context-Aware Observability** | `logger.bind()` for structured logs   |

## Creating a New Skill

Use `_template` as a scaffold for new skills:

### 1. Copy Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Add Commands (`tools.py`)

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

### 3. (Optional) Subprocess Mode

For heavy/conflicting dependencies, use the shim pattern:

```python
# tools.py - Lightweight shim
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).parent

def _run_isolated(command: str, **kwargs):
    cmd = ["uv", "run", "-q", "python", str(SKILL_DIR / "implementation.py"), command, json.dumps(kwargs)]
    result = subprocess.run(cmd, cwd=str(SKILL_DIR), capture_output=True, text=True)
    return result.stdout.strip()

@skill_command(name="heavy_op", description="Heavy operation")
def heavy_op(param: str) -> str:
    return _run_isolated("heavy_op", param=param)
```

```python
# implementation.py - Business logic
import heavy_library
# Implementation with heavy imports
```

### 4. (Optional) Add `repomix.json` for atomic context

```json
{
  "output": { "style": "xml", "fileSummary": true },
  "include": ["SKILL.md", "tools.py", "guide.md"],
  "ignore": { "patterns": [], "characters": [] }
}
```

### 5. Update `SKILL.md` with skill-specific guidelines

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [ODF-EP Planning Prompt](../../.claude/plans/odf-ep-v6-planning-prompt.md)
- [mcp-core-architecture](../../docs/developer/mcp-core-architecture.md)
