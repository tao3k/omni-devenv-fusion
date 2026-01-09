# Skill Templates (ODF-EP v7.0)

Centralized Jinja2 templates for skill generation with **Isolated Sandbox + Explicit Routing** architecture.

## Architecture

```
skill/
├── SKILL.md           # Skill metadata (YAML Frontmatter)
├── tools.py           # Router (just dispatches to scripts/)
└── scripts/           # Controllers (actual implementation)
    ├── __init__.py    # Package marker (required for isolation)
    ├── example.py     # Atomic implementation
    └── ...
```

**Key Design Principles:**

1. **Router-Controller Pattern**: `tools.py` only routes, `scripts/` implements
2. **Namespace Isolation**: `__init__.py` in `scripts/` prevents conflicts
3. **Explicit Relative Imports**: `from .scripts import x` instead of global imports

## Templates

| Template                 | Target                | Description                           |
| ------------------------ | --------------------- | ------------------------------------- |
| `SKILL.md.j2`            | `SKILL.md`            | Skill metadata with YAML Frontmatter  |
| `tools.py.j2`            | `tools.py`            | Router with @skill_command decorators |
| `scripts/__init__.py.j2` | `scripts/__init__.py` | Package exports                       |
| `guide.md.j2`            | `guide.md`            | Procedural documentation for LLM      |

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
