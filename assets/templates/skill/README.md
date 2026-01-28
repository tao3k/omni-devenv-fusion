# Skill Templates (ODF-EP v7.0)

Centralized Jinja2 templates for skill generation with **Isolated Sandbox + Explicit Routing** architecture.

## Architecture

```
skill/
├── SKILL.md           # Skill metadata (YAML Frontmatter)
└── scripts/           # Commands (actual implementation)
    ├── __init__.py    # Package marker (required for isolation)
    └── commands.py    # @skill_command decorated functions
```

**Key Design Principles:**

1. **No tools.py:** All commands live in `scripts/commands.py`
2. **Namespace Isolation:** `__init__.py` in `scripts/` prevents conflicts
3. **Explicit Relative Imports:** Use standard Python imports

## Templates

| Template                 | Target                | Description                          |
| ------------------------ | --------------------- | ------------------------------------ |
| `SKILL.md.j2`            | `SKILL.md`            | Skill metadata with YAML Frontmatter |
| `scripts/__init__.py.j2` | `scripts/__init__.py` | Package exports                      |
| `scripts/commands.py.j2` | `scripts/commands.py` | @skill_command decorated commands    |
| `guide.md.j2`            | `guide.md`            | Procedural documentation for LLM     |

## Usage

```python
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

template_dir = Path("assets/templates/skill")
env = Environment(loader=FileSystemLoader(str(template_dir)))

template = env.get_template("SKILL.md.j2")
output = template.render(
    skill_name="my_skill",
    description="My new skill",
    author="me",
)

# Write to skill directory
(output_path / "SKILL.md").write_text(output)
```

## Configuration

Templates are configured in `assets/settings.yaml` under `skill_architecture.templates`.

## See Also

- [Skills Documentation](../../docs/skills.md)
- [ODF-EP v7.0 Standards](../../assets/settings.yaml)
